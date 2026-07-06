# automation/utils.py
import asyncio
import random
import logging
from playwright.async_api import BrowserContext

logger = logging.getLogger(__name__)

async def human_delay(min_ms: int = 500, max_ms: int = 2000):
    """Introduces a randomized delay to mimic human behavior."""
    delay = random.uniform(min_ms / 1000.0, max_ms / 1000.0)
    await asyncio.sleep(delay)

async def inject_linkedin_cookies(context: BrowserContext, li_at_value: str):
    """Injects a LinkedIn session cookie into the browser context."""
    cookies = [
        {
            "name": "li_at",
            "value": li_at_value,
            "domain": ".linkedin.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "None"
        }
    ]
    await context.add_cookies(cookies)
    logger.info("Successfully injected LinkedIn session cookies.")

async def take_screenshot_on_failure(page, filename: str = "failure_screenshot.png"):
    """Takes a screenshot of the page for debugging selector issues."""
    try:
        await page.screenshot(path=filename, full_page=True)
        logger.info(f"Saved failure screenshot to {filename}")
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
