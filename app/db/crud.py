# app/db/crud.py
from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, Resume, Job, Application, UserSession

# --- User CRUD ---

async def get_user_by_telegram_id(db: AsyncSession, telegram_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalars().first()

async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """Get user by their database primary key ID (not telegram_id)."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


async def create_user(db: AsyncSession, telegram_id: int) -> User:
    user = User(telegram_id=telegram_id)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def get_or_create_user(db: AsyncSession, telegram_id: int) -> User:
    user = await get_user_by_telegram_id(db, telegram_id)
    if not user:
        user = await create_user(db, telegram_id)
    return user

async def update_user_profile(
    db: AsyncSession,
    user_id: int,
    preferred_role: Optional[str] = None,
    experience_years: Optional[float] = None,
    locations: Optional[List[str]] = None
) -> Optional[User]:
    update_data = {}
    if preferred_role is not None:
        update_data["preferred_role"] = preferred_role
    if experience_years is not None:
        update_data["experience_years"] = experience_years
    if locations is not None:
        update_data["locations"] = locations

    if update_data:
        await db.execute(
            update(User).where(User.id == user_id).values(**update_data)
        )
        await db.commit()
    
    # Return updated user
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()


# --- Resume CRUD ---

async def get_latest_resume(db: AsyncSession, user_id: int) -> Optional[Resume]:
    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(desc(Resume.version))
        .limit(1)
    )
    return result.scalars().first()

async def create_resume(
    db: AsyncSession,
    user_id: int,
    storage_path: str,
    ats_score: Optional[float] = None,
    approved_keywords: Optional[List[str]] = None
) -> Resume:
    latest = await get_latest_resume(db, user_id)
    next_version = (latest.version + 1) if latest else 1

    resume = Resume(
        user_id=user_id,
        version=next_version,
        storage_path=storage_path,
        ats_score=ats_score,
        approved_keywords=approved_keywords or []
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


# --- Job CRUD ---

async def create_job(
    db: AsyncSession,
    source: str,
    title: str,
    company: str,
    description: str,
    apply_link: str,
    requirements: Optional[dict] = None
) -> Job:
    job = Job(
        source=source,
        title=title,
        company=company,
        description=description,
        apply_link=apply_link,
        requirements=requirements or {}
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job

async def get_job_by_id(db: AsyncSession, job_id: int) -> Optional[Job]:
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalars().first()

async def get_unapplied_jobs(db: AsyncSession, user_id: int, limit: int = 10) -> List[Job]:
    # Select jobs that the user hasn't applied to yet
    subquery = select(Application.job_id).where(Application.user_id == user_id)
    result = await db.execute(
        select(Job)
        .where(Job.id.not_in(subquery))
        .order_by(desc(Job.found_at))
        .limit(limit)
    )
    return list(result.scalars().all())


# --- Application CRUD ---

async def create_application(
    db: AsyncSession,
    user_id: int,
    job_id: int,
    resume_id: Optional[int],
    status: str = "pending"
) -> Application:
    app = Application(
        user_id=user_id,
        job_id=job_id,
        resume_id=resume_id,
        status=status
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app

async def update_application_status(
    db: AsyncSession,
    application_id: int,
    status: str,
    applied_at: Optional[datetime] = None
) -> Optional[Application]:
    values = {"status": status}
    if applied_at:
        values["applied_at"] = applied_at
    elif status == "applied":
        values["applied_at"] = datetime.utcnow()

    await db.execute(
        update(Application)
        .where(Application.id == application_id)
        .values(**values)
    )
    await db.commit()

    result = await db.execute(select(Application).where(Application.id == application_id))
    return result.scalars().first()


# --- UserSession CRUD ---

async def get_user_session(db: AsyncSession, user_id: int, platform: str) -> Optional[UserSession]:
    result = await db.execute(
        select(UserSession)
        .where(UserSession.user_id == user_id, UserSession.platform == platform)
    )
    return result.scalars().first()

async def save_user_session(
    db: AsyncSession,
    user_id: int,
    platform: str,
    encrypted_cookie: str
) -> UserSession:
    session = await get_user_session(db, user_id, platform)
    if session:
        session.encrypted_cookie = encrypted_cookie
        session.updated_at = datetime.utcnow()
    else:
        session = UserSession(
            user_id=user_id,
            platform=platform,
            encrypted_cookie=encrypted_cookie
        )
        db.add(session)
    
    await db.commit()
    await db.refresh(session)
    return session
