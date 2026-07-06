# app/services/github_actions.py
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

async def trigger_job_search(user_id: int, role: str, locations: list[str]) -> bool:
    """
    Triggers the GitHub Actions daily-search or search-jobs workflow.
    """
    url = f"https://api.github.com/repos/{settings.GITHUB_OWNER}/{settings.GITHUB_REPO}/actions/workflows/search-jobs.yml/dispatches"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    payload = {
        "ref": "main",
        "inputs": {
            "user_id": str(user_id),
            "role": role,
            "locations": ", ".join(locations)
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Triggering GitHub Actions job search for user {user_id}...")
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 204:
                logger.info("Successfully dispatched search-jobs workflow.")
                return True
            else:
                logger.error(f"GitHub API returned status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error triggering GitHub workflow: {e}")
            return False

async def trigger_job_apply(user_id: int, job_id: int, resume_path: str) -> bool:
    """
    Triggers the GitHub Actions apply-job workflow.
    """
    url = f"https://api.github.com/repos/{settings.GITHUB_OWNER}/{settings.GITHUB_REPO}/actions/workflows/apply-job.yml/dispatches"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    payload = {
        "ref": "main",
        "inputs": {
            "user_id": str(user_id),
            "job_id": str(job_id),
            "resume_path": resume_path
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Triggering GitHub Actions auto-apply for user {user_id}, job {job_id}...")
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 204:
                logger.info("Successfully dispatched apply-job workflow.")
                return True
            else:
                logger.error(f"GitHub API returned status {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error triggering GitHub apply workflow: {e}")
            return False
