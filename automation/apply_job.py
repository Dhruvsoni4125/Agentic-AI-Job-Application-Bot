# automation/apply_job.py
import sys
import os
import argparse
import asyncio
import logging
import tempfile
from datetime import datetime
from playwright.async_api import async_playwright

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import async_session_maker
from app.db import crud
from app.security import decrypt_cookie
from app.services import storage
from automation.utils import human_delay, inject_linkedin_cookies, take_screenshot_on_failure

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def run_linkedin_apply(apply_link: str, li_at_cookie: str, resume_file_path: str) -> bool:
    """
    Automates LinkedIn Easy Apply using cookies and Playwright.
    """
    logger.info("Starting LinkedIn Easy Apply automation...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # User-Agent to avoid detection
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        
        page = await context.new_page()
        
        # Inject cookies before navigating
        await inject_linkedin_cookies(context, li_at_cookie)
        
        try:
            logger.info(f"Navigating to job page: {apply_link}")
            await page.goto(apply_link, wait_until="domcontentloaded")
            await human_delay(2000, 4000)
            
            # Check if Easy Apply button is present
            # Selector for LinkedIn Easy Apply button (can vary, standard is below)
            easy_apply_button = await page.query_selector("button.jobs-apply-button")
            
            if not easy_apply_button:
                logger.warning("No 'Easy Apply' button found. It might be a regular apply link or cookies expired.")
                await take_screenshot_on_failure(page, "apply_not_found.png")
                return False
                
            button_text = (await easy_apply_button.inner_text()).strip()
            if "Easy Apply" not in button_text:
                logger.warning(f"Apply button found, but text is '{button_text}', not 'Easy Apply'.")
                await take_screenshot_on_failure(page, "apply_button_mismatch.png")
                return False
                
            logger.info("Found Easy Apply button. Clicking it...")
            await easy_apply_button.click()
            await human_delay(1500, 3000)
            
            # Now, walk through the modal forms
            # We loop since there can be multiple steps: Contact Info -> Resume -> Custom Questions -> Review -> Submit
            max_steps = 10
            for step in range(max_steps):
                logger.info(f"Processing application form step {step + 1}...")
                await human_delay(1000, 2000)
                
                # Check if we can find file upload input (resume step)
                file_input = await page.query_selector("input[type='file']")
                if file_input:
                    logger.info("Found file upload input. Uploading optimized resume...")
                    await file_input.set_input_files(resume_file_path)
                    await human_delay(1500, 3000)
                    
                # Look for form navigation buttons: Next, Review, Submit
                next_button = await page.query_selector("button[aria-label*='next'], button[aria-label*='Next']")
                review_button = await page.query_selector("button[aria-label*='Review'], button[aria-label*='review']")
                submit_button = await page.query_selector("button[aria-label*='Submit'], button[aria-label*='submit']")
                
                if submit_button:
                    # Double check if we are on the final screen or if we can click it
                    logger.info("Found 'Submit application' button. Submitting...")
                    await submit_button.click()
                    await human_delay(3000, 5000)
                    logger.info("Application submitted successfully!")
                    return True
                    
                if review_button:
                    logger.info("Found 'Review' button. Clicking...")
                    await review_button.click()
                    continue
                    
                if next_button:
                    logger.info("Found 'Next' button. Clicking...")
                    await next_button.click()
                    continue
                    
                # If no standard buttons found, maybe there's custom required questions we didn't fill
                logger.warning("Stuck on a step. No navigation buttons detected. Selector drift or custom questions blocking.")
                await take_screenshot_on_failure(page, "apply_form_stuck.png")
                return False
                
            logger.warning("Reached maximum steps limit without submitting application.")
            await take_screenshot_on_failure(page, "apply_steps_limit.png")
            return False
            
        except Exception as e:
            logger.error(f"Error during application process: {e}")
            await take_screenshot_on_failure(page, "apply_exception.png")
            return False
        finally:
            await browser.close()

async def main():
    parser = argparse.ArgumentParser(description="Run Playwright job application.")
    parser.add_argument("--user_id", type=int, required=True, help="User ID applying")
    parser.add_argument("--job_id", type=int, required=True, help="Job ID to apply for")
    parser.add_argument("--resume_path", type=str, required=True, help="Storage path of resume to download")
    args = parser.parse_args()
    
    # 1. Fetch details from DB
    async with async_session_maker() as db:
        user = await crud.get_user_by_id(db, args.user_id)
        job = await crud.get_job_by_id(db, args.job_id)
        
        if not user or not job:
            logger.error("User or Job record not found in database.")
            sys.exit(1)
            
        # Get cookies
        session = await crud.get_user_session(db, user.id, "linkedin")
        if not session or not session.encrypted_cookie:
            logger.error(f"No cookies configured for LinkedIn for user {args.user_id}")
            sys.exit(1)
            
        # Decrypt cookie
        li_at_cookie = decrypt_cookie(session.encrypted_cookie)

    # 2. Download resume PDF from Supabase Storage
    logger.info(f"Downloading resume from storage: {args.resume_path}")
    temp_dir = tempfile.gettempdir()
    temp_resume_path = os.path.join(temp_dir, f"apply_resume_{args.user_id}.pdf")
    
    try:
        resume_bytes = storage.download_file("resumes", args.resume_path)
        with open(temp_resume_path, "wb") as f:
            f.write(resume_bytes)
    except Exception as e:
        logger.error(f"Failed to download resume PDF: {e}")
        sys.exit(1)

    # 3. Run Easy Apply
    success = await run_linkedin_apply(
        apply_link=job.apply_link,
        li_at_cookie=li_at_cookie,
        resume_file_path=temp_resume_path
    )
    
    # 4. Cleanup resume
    if os.path.exists(temp_resume_path):
        os.remove(temp_resume_path)
        
    # 5. Update DB Status
    status = "applied" if success else "failed"
    async with async_session_maker() as db:
        # Check if application already exists, if not create one, then update status
        from sqlalchemy import select
        from app.db.models import Application
        result = await db.execute(
            select(Application).where(Application.user_id == user.id, Application.job_id == job.id)
        )
        app = result.scalars().first()
        if not app:
            # Get latest resume record ID
            resume_record = await crud.get_latest_resume(db, user.id)
            app = await crud.create_application(
                db,
                user_id=user.id,
                job_id=job.id,
                resume_id=resume_record.id if resume_record else None,
                status=status
            )
            
        await crud.update_application_status(db, app.id, status=status, applied_at=datetime.utcnow() if success else None)
        
    if success:
        logger.info("Application flow completed successfully.")
        # Trigger an alert/message to user (can be done via FastAPI webhook or similar in staging/prod)
    else:
        logger.error("Application flow failed.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
