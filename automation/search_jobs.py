# automation/search_jobs.py
import sys
import os
import argparse
import asyncio
import logging
from urllib.parse import quote
from playwright.async_api import async_playwright

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import async_session_maker
from app.db import crud
from automation.utils import human_delay, take_screenshot_on_failure

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def search_linkedin_jobs(role: str, location: str, limit: int = 10):
    """
    Scrapes LinkedIn's public job search page for listings.
    Does not require login, reducing account ban risk.
    """
    logger.info(f"Searching LinkedIn jobs for '{role}' in '{location}'...")
    search_url = f"https://www.linkedin.com/jobs/search?keywords={quote(role)}&location={quote(location)}"
    
    jobs_found = []
    
    async with async_playwright() as p:
        # Launch browser (headless by default in CI)
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        # Open a new page with a standard User-Agent
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            await page.goto(search_url, wait_until="domcontentloaded")
            await page.wait_for_selector(".jobs-search__results-list", timeout=15000)
            
            # Scroll down to load more jobs
            for _ in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await human_delay(800, 1500)
                
            # Extract job cards
            job_cards = await page.query_selector_all(".jobs-search__results-list li")
            logger.info(f"Found {len(job_cards)} job cards on page.")
            
            count = 0
            for card in job_cards:
                if count >= limit:
                    break
                    
                try:
                    # Get title
                    title_elem = await card.query_selector(".base-search-card__title")
                    title = (await title_elem.inner_text()).strip() if title_elem else ""
                    
                    # Get company
                    company_elem = await card.query_selector(".base-search-card__subtitle")
                    company = (await company_elem.inner_text()).strip() if company_elem else ""
                    
                    # Get link
                    link_elem = await card.query_selector("a.base-card__full-link")
                    apply_link = await link_elem.get_attribute("href") if link_elem else ""
                    
                    if not title or not apply_link:
                        continue
                        
                    # Clean apply link (remove tracking params)
                    if "?" in apply_link:
                        apply_link = apply_link.split("?")[0]
                        
                    jobs_found.append({
                        "title": title,
                        "company": company,
                        "apply_link": apply_link,
                        "source": "linkedin"
                    })
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to parse job card: {e}")
                    
            # For each job found, fetch its description
            for job in jobs_found:
                logger.info(f"Fetching description for: {job['title']} at {job['company']}")
                try:
                    await page.goto(job["apply_link"], wait_until="domcontentloaded")
                    await human_delay(1000, 2000)
                    
                    # Click show more if present
                    show_more_button = await page.query_selector(".show-more-less-html__button")
                    if show_more_button:
                        await show_more_button.click()
                        await human_delay(300, 600)
                        
                    desc_elem = await page.query_selector(".show-more-less-html__markup")
                    if desc_elem:
                        job["description"] = (await desc_elem.inner_text()).strip()
                    else:
                        job["description"] = "No description found."
                except Exception as e:
                    logger.warning(f"Failed to fetch job description for {job['title']}: {e}")
                    job["description"] = "Failed to fetch description."
                    
        except Exception as e:
            logger.error(f"Error during job search scraping: {e}")
            await take_screenshot_on_failure(page, "search_failure.png")
        finally:
            await browser.close()
            
    return jobs_found

async def main():
    parser = argparse.ArgumentParser(description="Run Playwright job search and save to database.")
    parser.add_argument("--user_id", type=int, required=True, help="User ID running the search")
    parser.add_argument("--role", type=str, required=True, help="Preferred role to search")
    parser.add_argument("--locations", type=str, required=True, help="Locations comma separated")
    args = parser.parse_args()
    
    locations = [loc.strip() for loc in args.locations.split(",") if loc.strip()]
    if not locations:
        locations = ["Remote"]
        
    all_jobs = []
    # Search for each location
    for loc in locations:
        jobs = await search_linkedin_jobs(args.role, loc, limit=5)
        all_jobs.extend(jobs)
        
    if not all_jobs:
        logger.info("No jobs found matching criteria.")
        return
        
    # Write to DB
    logger.info(f"Saving {len(all_jobs)} jobs to the database...")
    async with async_session_maker() as db:
        for job in all_jobs:
            try:
                # Add check to prevent duplicates
                # We can check if a job with same title, company, and link already exists
                from sqlalchemy import select
                from app.db.models import Job
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
                        description=job["description"],
                        apply_link=job["apply_link"]
                    )
            except Exception as e:
                logger.error(f"Failed to write job '{job['title']}' to database: {e}")

if __name__ == "__main__":
    asyncio.run(main())
