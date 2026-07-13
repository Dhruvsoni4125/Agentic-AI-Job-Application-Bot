# app/bot/handlers.py
import os
import tempfile
import logging
from typing import Optional
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.bot.bot import (
    bot,
    Onboarding, CookieAuth, OptimizeFlow,
    get_main_menu_keyboard,
    get_platform_keyboard,
    get_yes_no_keyboard,
    get_template_keyboard,
    get_keyword_approval_keyboard,
    get_apply_confirmation_keyboard
)
from app.db.database import async_session_maker
from app.db import crud
from app.security import encrypt_cookie
from app.services import (
    resume_parser,
    storage,
    resume_optimizer,
    ats_scorer,
    pdf_generator,
    github_actions
)

logger = logging.getLogger(__name__)
router = Router()

# Helper to respond to unrecognized commands/messages
async def send_welcome_and_start_onboarding(message: Message, state: FSMContext):
    await state.set_state(Onboarding.waiting_resume)
    await message.answer(
        "👋 Welcome to the AI Resume Optimizer & Auto Job Apply Bot!\n\n"
        "Let's get you set up. Please upload your current Resume (.pdf or .docx format):",
        reply_markup=types.ReplyKeyboardRemove()
    )

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    async with async_session_maker() as db:
        await crud.get_or_create_user(db, message.from_user.id)
    await state.update_data(is_onboarding=True)
    await send_welcome_and_start_onboarding(message, state)

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "🤖 **AI Resume Optimizer & Auto Job Apply Bot**\n\n"
        "Here's what I can do:\n\n"
        "📄 **Upload/Update Resume** — Upload your resume (.pdf or .docx) for parsing and optimization.\n"
        "🔑 **Configure Session Cookies** — Set up your LinkedIn session cookie for auto-apply.\n"
        "🔍 **Search Jobs** — Trigger Playwright-powered job searches on LinkedIn and Naukri.\n"
        "⚡ **Optimize Resume (ATS)** — Paste a Job Description and get ATS scoring + an optimized resume PDF.\n"
        "📋 **Application History** — View your recent job applications and their statuses.\n\n"
        "**Commands:**\n"
        "/start — Re-run onboarding\n"
        "/help — Show this help message\n\n"
        "💡 Tip: Start by uploading your resume, then configure cookies, and search for jobs!"
    )
    await message.answer(help_text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())

# --- Onboarding FSM Flow ---

@router.message(Onboarding.waiting_resume, F.document)
async def handle_onboarding_resume(message: Message, state: FSMContext):
    document = message.document
    filename = document.file_name
    _, ext = os.path.splitext(filename.lower())
    
    if ext not in [".pdf", ".docx", ".doc"]:
        await message.answer("❌ Invalid file format. Please upload a PDF or Word (.docx) file.")
        return

    msg_status = await message.answer("⏳ Downloading and parsing your resume...")
    
    # Create temp file
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"resume_{message.from_user.id}{ext}")
    
    try:
        # Download file from Telegram
        file = await bot.get_file(document.file_id)
        await bot.download_file(file.file_path, temp_path)
        
        # Parse Text
        resume_text = await resume_parser.parse_resume(temp_path)
        
        # Upload original PDF to Supabase Storage
        with open(temp_path, "rb") as f:
            file_bytes = f.read()
            
        content_type = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        storage_path = f"resumes/{message.from_user.id}/original_{filename}"
        
        storage.upload_file("resumes", storage_path, file_bytes, content_type)
        
        # Store temporary data in FSM
        await state.update_data(
            resume_text=resume_text,
            storage_path=storage_path,
            filename=filename
        )
        
        # Check if user already has a profile (Update Resume flow vs Onboarding)
        state_data = await state.get_data()
        is_onboarding = state_data.get("is_onboarding", False)
        
        async with async_session_maker() as db:
            user = await crud.get_or_create_user(db, message.from_user.id)
            if user.preferred_role and not is_onboarding:
                # User already has a profile — just save the new resume
                await crud.create_resume(
                    db,
                    user_id=user.id,
                    storage_path=storage_path,
                    approved_keywords=[]
                )
                await msg_status.delete()
                await state.clear()
                await message.answer(
                    "✅ Resume updated successfully!\n\n"
                    "Your new resume has been saved. You can now optimize it against a Job Description.",
                    reply_markup=get_main_menu_keyboard()
                )
                return
        
        await msg_status.delete()
        await state.set_state(Onboarding.waiting_role)
        await message.answer("✅ Resume parsed successfully!\n\nWhat is your preferred job role? (e.g., Software Engineer)")
    except resume_parser.ParsingException as e:
        await msg_status.edit_text(f"⚠️ Parsing issue: {str(e)}\n\nPlease try uploading a different document.")
    except Exception as e:
        logger.exception("Error in handle_onboarding_resume")
        await msg_status.edit_text("❌ An unexpected error occurred. Please try again.")
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

@router.message(Onboarding.waiting_resume)
async def handle_onboarding_resume_text(message: Message, state: FSMContext):
    """Catch non-document messages while waiting for resume upload."""
    await message.answer("📄 Please upload a resume file (.pdf or .docx). Text input is not supported here.")

@router.message(Onboarding.waiting_role)
async def handle_onboarding_role(message: Message, state: FSMContext):
    role = message.text.strip()
    if not role:
        await message.answer("Please enter a valid job role.")
        return
        
    await state.update_data(preferred_role=role)
    await state.set_state(Onboarding.waiting_experience)
    await message.answer("How many years of professional experience do you have?")

@router.message(Onboarding.waiting_experience)
async def handle_onboarding_experience(message: Message, state: FSMContext):
    try:
        years = float(message.text.strip())
        if years < 0:
            raise ValueError
    except ValueError:
        await message.answer("Please enter a valid positive number for years of experience.")
        return
        
    await state.update_data(experience_years=years)
    await state.set_state(Onboarding.waiting_locations)
    await message.answer("What are your preferred job locations? (e.g., New York, Remote - comma separated)")

@router.message(Onboarding.waiting_locations)
async def handle_onboarding_locations(message: Message, state: FSMContext):
    locations_raw = message.text.split(",")
    locations = [loc.strip() for loc in locations_raw if loc.strip()]
    
    if not locations:
        await message.answer("Please enter at least one location.")
        return

    data = await state.get_data()
    
    async with async_session_maker() as db:
        # Get user
        user = await crud.get_or_create_user(db, message.from_user.id)
        
        # Save user profile
        await crud.update_user_profile(
            db,
            user_id=user.id,
            preferred_role=data["preferred_role"],
            experience_years=data["experience_years"],
            locations=locations
        )
        
        # Save Resume Entry
        await crud.create_resume(
            db,
            user_id=user.id,
            storage_path=data["storage_path"],
            approved_keywords=[]
        )
        
    await state.clear()
    await message.answer(
        "🎉 Profile Setup Complete!\n\n"
        "You can now manage your configurations or start searching & optimizing resumes using the menu below.",
        reply_markup=get_main_menu_keyboard()
    )


# --- Main Menu Button Handlers ---

@router.message(F.text == "📄 Upload/Update Resume")
async def cmd_update_resume(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Onboarding.waiting_resume)
    await message.answer("Please upload your new Resume document (.pdf or .docx):")

@router.message(F.text == "🔑 Configure Session Cookies")
async def cmd_configure_cookies(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(CookieAuth.waiting_platform)
    await message.answer("Choose the platform to set up cookies for:", reply_markup=get_platform_keyboard())

@router.message(F.text == "📋 Application History")
async def cmd_application_history(message: Message):
    async with async_session_maker() as db:
        user = await crud.get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("User profile not found. Run /start first.")
            return
            
        # Get user's applications
        from sqlalchemy import select
        from app.db.models import Application, Job
        result = await db.execute(
            select(Application, Job)
            .join(Job, Application.job_id == Job.id)
            .where(Application.user_id == user.id)
            .order_by(Application.created_at.desc())
            .limit(10)
        )
        apps = result.all()
        
    if not apps:
        await message.answer("You haven't applied to any jobs yet!")
        return

    text = "📋 **Your Recent Applications:**\n\n"
    for app, job in apps:
        status_str = app.status or "unknown"
        source_str = job.source or "other"
        status_emoji = {
            "applied": "✅",
            "pending": "⏳",
            "failed": "❌",
            "rejected": "💔",
            "skipped": "⏭️"
        }.get(status_str, "📝")
        text += f"{status_emoji} **{job.title or 'Untitled'}** at *{job.company or 'Unknown'}*\n"
        text += f"   • Platform: {source_str.capitalize()}\n"
        text += f"   • Status: {status_str.capitalize()}\n"
        if app.applied_at:
            text += f"   • Applied: {app.applied_at.strftime('%Y-%m-%d')}\n"
        text += "\n"
        
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "🔍 Search Jobs")
async def cmd_search_jobs(message: Message):
    async with async_session_maker() as db:
        user = await crud.get_user_by_telegram_id(db, message.from_user.id)
        if not user or not user.preferred_role:
            await message.answer("Please complete your onboarding profile by typing /start.")
            return
        
        # Check if there are recently scraped jobs matching the role
        unapplied_jobs = await crud.get_unapplied_jobs(db, user.id, limit=5)
        
        # Store user info for use outside the session
        user_id = user.id
        user_role = user.preferred_role
        user_locations = user.locations or []
        
    # Trigger background search anyway
    success = await github_actions.trigger_job_search(
        user_id=user_id,
        role=user_role,
        locations=user_locations
    )
    
    if not success:
        logger.error("Failed to trigger job search GitHub actions workflow")

    if unapplied_jobs:
        await message.answer(
            f"🔍 Triggered a fresh job search in the background for *'{user_role}'*.\n\n"
            f"Meanwhile, here are some unapplied jobs found in our database:",
            parse_mode="Markdown"
        )
        for job in unapplied_jobs:
            source_str = job.source or "other"
            job_text = (
                f"💼 **{job.title or 'Untitled'}**\n"
                f"🏢 Company: {job.company or 'Unknown'}\n"
                f"🌐 Source: {source_str.capitalize()}\n"
                f"🔗 Link: [View Job]({job.apply_link})\n"
            )
            # Send job item with inline options
            builder = InlineKeyboardBuilder()
            builder.button(text="⚡ Optimize & Apply", callback_data=f"opt:{job.id}")
            await message.answer(job_text, reply_markup=builder.as_markup(), parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await message.answer(
            f"🔍 Triggered fresh job search workflows in the background for *'{user_role}'*.\n\n"
            "We will scan LinkedIn and Naukri for your locations: " + ", ".join(user_locations) + ".\n"
            "You will be notified once matching jobs are processed!",
            parse_mode="Markdown"
        )


# --- Cookie Authorization Callback Handlers ---

@router.callback_query(F.data.startswith("platform:"))
async def handle_cookie_platform(callback: CallbackQuery, state: FSMContext):
    platform = callback.data.split(":")[1]
    await state.update_data(platform=platform)
    await state.set_state(CookieAuth.waiting_cookie)

    if platform != "linkedin":
        await callback.message.edit_text(
            "⚠️ Only LinkedIn cookie automation is supported right now.\n\nPlease choose LinkedIn to continue.",
            parse_mode="Markdown"
        )
        await state.clear()
        await callback.answer()
        return
    
    instructions = {
        "linkedin": (
            "🔑 **LinkedIn Cookie Setup**:\n\n"
            "1. Log into LinkedIn on your desktop browser.\n"
            "2. Open Developer Tools (F12) -> Application (Chrome) or Storage (Firefox) -> Cookies.\n"
            "3. Find the cookie named `li_at` and copy its value.\n"
            "4. Paste and send the `li_at` value directly here."
        )
    }.get(platform, "Please send your session cookie string.")

    await callback.message.edit_text(instructions, parse_mode="Markdown")
    await callback.answer()

@router.message(CookieAuth.waiting_cookie)
async def handle_cookie_input(message: Message, state: FSMContext):
    cookie_str = message.text.strip()
    data = await state.get_data()
    platform = data["platform"]
    
    # Encrypt
    encrypted = encrypt_cookie(cookie_str)
    
    async with async_session_maker() as db:
        user = await crud.get_user_by_telegram_id(db, message.from_user.id)
        if user:
            await crud.save_user_session(db, user_id=user.id, platform=platform, encrypted_cookie=encrypted)
            
    await state.clear()
    await message.answer(
        f"✅ Successfully saved your encrypted {platform.capitalize()} session cookie!\n"
        f"This cookie will be used securely inside Playwright to apply for jobs.",
        reply_markup=get_main_menu_keyboard()
    )


# --- Optimize Flow Handlers ---

@router.message(F.text == "⚡ Optimize Resume (ATS)")
async def cmd_optimize_ats(message: Message, state: FSMContext):
    await state.clear()
    async with async_session_maker() as db:
        user = await crud.get_user_by_telegram_id(db, message.from_user.id)
        if not user:
            await message.answer("User profile not found. Run /start first.")
            return
        
        resume = await crud.get_latest_resume(db, user.id)
        if not resume:
            await message.answer("❌ You haven't uploaded a resume yet. Please upload one first.")
            await state.set_state(Onboarding.waiting_resume)
            return

    await state.set_state(OptimizeFlow.waiting_jd)
    await message.answer(
        "⚡ **ATS Optimization**\n\n"
        "Please paste the text of the Job Description (JD) you want to optimize your resume for:"
    )

@router.callback_query(F.data.startswith("opt:"))
async def handle_inline_optimize(callback: CallbackQuery, state: FSMContext):
    job_id = int(callback.data.split(":")[1])
    await state.clear()
    
    async with async_session_maker() as db:
        user = await crud.get_user_by_telegram_id(db, callback.from_user.id)
        resume = await crud.get_latest_resume(db, user.id) if user else None
        job = await crud.get_job_by_id(db, job_id)
        
    if not resume:
        await callback.message.answer("❌ You need to upload a resume first. Run /start.")
        await callback.answer()
        return
        
    if not job:
        await callback.message.answer("❌ Job details not found.")
        await callback.answer()
        return

    # Trigger optimization flow using job in database
    await callback.message.answer(f"⚡ Selected job: *{job.title}* at *{job.company}*. Starting ATS evaluation...", parse_mode="Markdown")
    await run_ats_optimization(callback.message, state, resume, job.description, job_id)
    await callback.answer()

@router.message(OptimizeFlow.waiting_jd)
async def handle_jd_input(message: Message, state: FSMContext):
    jd_text = message.text.strip()
    if len(jd_text) < 100:
        await message.answer("Job description seems too short. Please paste a full job description.")
        return

    async with async_session_maker() as db:
        user = await crud.get_user_by_telegram_id(db, message.from_user.id)
        resume = await crud.get_latest_resume(db, user.id) if user else None
        
    if not resume:
        await message.answer("❌ You need to upload a resume first. Run /start.")
        return
        
    await run_ats_optimization(message, state, resume, jd_text, job_id=None)

async def run_ats_optimization(message: Message, state: FSMContext, resume, jd_text: str, job_id: Optional[int]):
    msg_status = await message.answer("⏳ Extracting key requirements from JD and scoring your resume with Nemotron LLM...")
    
    try:
        # Load resume bytes from storage to parse text
        resume_bytes = storage.download_file("resumes", resume.storage_path)
        
        # Temp save resume to parse
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"eval_{message.from_user.id}.pdf")
        with open(temp_path, "wb") as f:
            f.write(resume_bytes)
            
        resume_text = await resume_parser.parse_resume(temp_path)
        os.remove(temp_path)
        
        # Extract JD skills
        extraction = await ats_scorer.extract_jd_details(jd_text)
        
        # Score Resume
        evaluation = await ats_scorer.evaluate_resume_ats(resume_text, jd_text, extraction.key_skills)
        
        # Save state data for next step
        await state.update_data(
            jd_text=jd_text,
            job_id=job_id,
            original_resume_text=resume_text,
            key_skills=extraction.key_skills,
            missing_keywords=evaluation["missing_keywords"],
            job_title=extraction.title,
            company=extraction.company
        )
        
        # Respond to user
        score_text = (
            f"📈 **ATS Evaluation Results:**\n\n"
            f"🎯 **Blended ATS Score:** `{evaluation['blended_score']}%`\n"
            f"   • Keyword Overlap: `{evaluation['keyword_overlap_score']}%`\n"
            f"   • LLM Match Rating: `{evaluation['llm_score']}/100`\n\n"
            f"🔑 **Matched Skills:** {', '.join(evaluation['matched_keywords']) or 'None'}\n\n"
            f"⚠️ **Missing Keywords:** {', '.join(evaluation['missing_keywords']) or 'None'}\n\n"
            f"✍️ **Action Verb Feedback:**\n_{evaluation['action_verb_feedback']}_\n\n"
            f"💡 **Top Suggestions:**\n"
        )
        for sug in evaluation["suggestions"]:
            score_text += f"• {sug}\n"
            
        score_text += "\nWould you like to rewrite and optimize your resume to include the missing keywords?"
        
        await msg_status.delete()
        await state.set_state(OptimizeFlow.waiting_keywords_approval)
        await message.answer(score_text, reply_markup=get_keyword_approval_keyboard(), parse_mode="Markdown")
        
    except Exception as e:
        logger.exception("Error during ATS scoring")
        await msg_status.edit_text("❌ Failed to complete ATS scoring. Please ensure your resume text is clean.")

@router.callback_query(OptimizeFlow.waiting_keywords_approval, F.data == "keywords:approve")
async def handle_keywords_approve(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OptimizeFlow.waiting_template_choice)
    await callback.message.edit_text(
        "🎨 **Choose a Resume Style Template:**\n\n"
        "• *Classic*: High ATS parsing compatibility, serif typography, clean borders.\n"
        "• *Modern*: Stylish layout, modern sans-serif typography, subtle blue accents.\n"
        "• *Creative*: Bold design with vibrant colors and modern visual hierarchy.",
        reply_markup=get_template_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(OptimizeFlow.waiting_keywords_approval, F.data == "keywords:custom")
async def handle_keywords_custom(callback: CallbackQuery, state: FSMContext):
    """Handle custom keywords input — user wants to specify their own keywords."""
    await state.set_state(OptimizeFlow.waiting_custom_keywords)
    await callback.message.edit_text(
        "✍️ **Custom Keywords**\n\n"
        "Please type the keywords you want to inject into your resume, separated by commas.\n\n"
        "Example: `Python, FastAPI, Docker, Kubernetes, CI/CD`",
        parse_mode="Markdown"
    )
    await callback.answer()

@router.message(OptimizeFlow.waiting_custom_keywords)
async def handle_custom_keywords_input(message: Message, state: FSMContext):
    """Process user-provided custom keywords and proceed to template selection."""
    keywords_raw = message.text.split(",")
    keywords = [kw.strip() for kw in keywords_raw if kw.strip()]
    
    if not keywords:
        await message.answer("Please enter at least one keyword, separated by commas.")
        return
    
    # Update missing_keywords with user-provided ones
    await state.update_data(missing_keywords=keywords)
    
    await state.set_state(OptimizeFlow.waiting_template_choice)
    await message.answer(
        f"✅ Using your custom keywords: {', '.join(keywords)}\n\n"
        "🎨 **Choose a Resume Style Template:**\n\n"
        "• *Classic*: High ATS parsing compatibility, serif typography, clean borders.\n"
        "• *Modern*: Stylish layout, modern sans-serif typography, subtle blue accents.\n"
        "• *Creative*: Bold design with vibrant colors and modern visual hierarchy.",
        reply_markup=get_template_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(OptimizeFlow.waiting_keywords_approval, F.data == "keywords:cancel")
async def handle_keywords_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Optimization cancelled.")
    await callback.message.answer("What would you like to do next?", reply_markup=get_main_menu_keyboard())
    await callback.answer()

@router.callback_query(OptimizeFlow.waiting_template_choice, F.data.startswith("template:"))
async def handle_template_choice(callback: CallbackQuery, state: FSMContext):
    template_name = callback.data.split(":")[1]
    data = await state.get_data()
    
    msg_status = await callback.message.edit_text("⏳ Generating optimized resume PDF with Nemotron LLM...")
    
    try:
        # Structure original resume text
        structured_orig = await resume_optimizer.structure_resume(data["original_resume_text"])
        
        # Optimize structured resume content
        structured_opt = await resume_optimizer.optimize_resume(
            original=structured_orig,
            jd_text=data["jd_text"],
            approved_keywords=data["missing_keywords"]
        )
        
        # Generate new PDF using WeasyPrint
        # Render using the optimized structured dict
        pdf_bytes = await pdf_generator.generate_resume_pdf(structured_opt.model_dump(), template_name)
        
        # Save optimized PDF to Supabase Storage
        job_title_safe = (data.get('job_title') or 'job').replace(' ', '_')
        storage_path = f"resumes/{callback.from_user.id}/optimized_{job_title_safe}.pdf"
        storage.upload_file("resumes", storage_path, pdf_bytes, "application/pdf")
        
        # Create database record for resume
        async with async_session_maker() as db:
            user = await crud.get_user_by_telegram_id(db, callback.from_user.id)
            new_resume = await crud.create_resume(
                db,
                user_id=user.id,
                storage_path=storage_path,
                ats_score=None,
                approved_keywords=data["missing_keywords"]
            )
            
            # Save or get job ID
            job_id = data.get("job_id")
            if not job_id:
                # Create job dynamically
                job = await crud.create_job(
                    db,
                    source="custom",
                    title=data.get("job_title", "Custom Job"),
                    company=data.get("company", "Unknown"),
                    description=data["jd_text"],
                    apply_link=""
                )
                job_id = job.id

        # Send optimized resume back to user
        temp_dir = tempfile.gettempdir()
        temp_pdf_path = os.path.join(temp_dir, f"optimized_{callback.from_user.id}.pdf")
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_bytes)
            
        await msg_status.delete()
        
        # Send Document
        await bot.send_document(
            chat_id=callback.message.chat.id,
            document=FSInputFile(temp_pdf_path, filename=f"Optimized_Resume_{job_title_safe}.pdf"),
            caption="✨ Here is your optimized resume tailored to the job description!"
        )
        os.remove(temp_pdf_path)
        
        # Ask to apply
        job_title_display = data.get('job_title', 'this job')
        company_display = data.get('company', 'the company')
        await callback.message.answer(
            f"Would you like to Auto-Apply to *{job_title_display}* at *{company_display}* using this new resume?",
            reply_markup=get_apply_confirmation_keyboard(job_id),
            parse_mode="Markdown"
        )
        await state.set_state(OptimizeFlow.waiting_apply_confirmation)
        
    except Exception as e:
        logger.exception("Error generating optimized resume")
        await callback.message.answer("❌ FAILED to generate optimized resume. Please try again.")
    await callback.answer()

@router.callback_query(OptimizeFlow.waiting_apply_confirmation, F.data.startswith("apply:"))
async def handle_apply_confirmation(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    job_id = int(parts[1])
    confirm = parts[2]
    
    async with async_session_maker() as db:
        user = await crud.get_user_by_telegram_id(db, callback.from_user.id)
        resume = await crud.get_latest_resume(db, user.id) if user else None
        job = await crud.get_job_by_id(db, job_id)
        
    if confirm == "yes":
        if not user or not resume:
            await callback.message.edit_text("❌ Missing user details or resume. Run /start.")
            await state.clear()
            await callback.answer()
            return
            
        # Verify user has session cookies
        async with async_session_maker() as db:
            session = await crud.get_user_session(db, user.id, "linkedin") # default to linkedin first
            
        if not session:
            await callback.message.edit_text(
                "❌ You haven't configured your session cookies yet!\n\n"
                "Please configure cookies first using *🔑 Configure Session Cookies* in the main menu.",
                parse_mode="Markdown"
            )
            await state.clear()
            await callback.answer()
            return
            
        # Trigger Auto Apply GitHub action
        # Get signed URL or storage path to pull resume
        success = await github_actions.trigger_job_apply(
            user_id=user.id,
            job_id=job.id,
            resume_path=resume.storage_path
        )
        
        if success:
            async with async_session_maker() as db:
                await crud.create_application(db, user_id=user.id, job_id=job.id, resume_id=resume.id, status="pending")
            job_title = job.title or "the job"
            job_company = job.company or "the company"
            await callback.message.edit_text(
                f"🚀 **Auto Apply Triggered!**\n\n"
                f"We are running Playwright in a secure GitHub Actions worker to fill and apply for "
                f"*{job_title}* at *{job_company}*.\n"
                f"You will be notified once the process is complete.",
                parse_mode="Markdown"
            )
        else:
            await callback.message.edit_text("❌ Failed to trigger the apply workflow. Please try again later.")
    else:
        if user and job:
            async with async_session_maker() as db:
                await crud.create_application(db, user_id=user.id, job_id=job.id, resume_id=resume.id if resume else None, status="skipped")
        await callback.message.edit_text("⏭️ Skipped. You can find this job under Search Jobs if you change your mind.")
        
    await state.clear()
    await callback.answer()
