# automation/daily_search.py
"""
Daily cron job script: iterates over all registered users with a preferred_role
and triggers LinkedIn job searches for each one.
Called by .github/workflows/daily-search.yml on a cron schedule.
"""
import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.database import async_session_maker
from app.db.models import User
from automation.search_jobs import search_linkedin_jobs
from app.db import crud

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    """Fetch all users with a preferred_role and run job search for each."""
    logger.info("Starting daily job search for all registered users...")

    async with async_session_maker() as db:
        result = await db.execute(
            select(User).where(User.preferred_role.isnot(None))
        )
        users = list(result.scalars().all())

    if not users:
        logger.info("No users with a configured preferred_role found. Exiting.")
        return

    logger.info(f"Found {len(users)} users to search jobs for.")

    for user in users:
        locations = user.locations or ["Remote"]
        role = user.preferred_role
        logger.info(f"Searching jobs for user {user.id} | role='{role}' | locations={locations}")

        all_jobs = []
        for loc in locations:
            try:
                jobs = await search_linkedin_jobs(role, loc, limit=5)
                all_jobs.extend(jobs)
            except Exception as e:
                logger.error(f"Error searching jobs for user {user.id} in location '{loc}': {e}")

        if not all_jobs:
            logger.info(f"No jobs found for user {user.id}.")
            continue

        # Write to DB, deduplicating by apply_link
        logger.info(f"Saving {len(all_jobs)} jobs for user {user.id}...")
        async with async_session_maker() as db:
            from app.db.models import Job
            for job in all_jobs:
                try:
                    result = await db.execute(
                        select(Job).where(Job.apply_link == job["apply_link"])
                    )
                    existing = result.scalars().first()
                    if not existing:
                        await crud.create_job(
                            db,
                            source=job["source"],
                            title=job["title"],
                            company=job["company"],
                            description=job.get("description", ""),
                            apply_link=job["apply_link"]
                        )
                except Exception as e:
                    logger.error(f"Failed to save job '{job['title']}': {e}")

    logger.info("Daily job search completed.")


if __name__ == "__main__":
    asyncio.run(main())
