# app/services/nemotron.py
import json
import logging
from typing import Optional, Type, TypeVar
import httpx
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

class NemotronException(Exception):
    """Custom exception for Nemotron API errors."""
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, NemotronException)),
    reraise=True
)
async def call_nemotron(
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = False,
    model_id: str = "meta/llama-3.1-70b-instruct"
) -> str:
    """
    Calls Nemotron-4-340b-instruct via NVIDIA NIM API.
    Retries on rate limits or network issues.
    """
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.NEMOTRON_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 1024 if json_mode else 2048
    }

    if json_mode:
        # Note: Some providers support response_format={"type": "json_object"},
        # check if integrate.api.nvidia.com supports it. To be safe, we request it in the prompt.
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            logger.info(f"Calling Nemotron API ({model_id})...")
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return content
        except httpx.HTTPStatusError as e:
            logger.error(f"NVIDIA NIM HTTP error: {e.response.status_code} - {e.response.text}")
            raise NemotronException(f"NVIDIA NIM returned status {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error calling Nemotron: {str(e)}")
            raise

async def call_nemotron_structured(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    model_id: str = "meta/llama-3.1-70b-instruct"
) -> T:
    """
    Calls Nemotron, requests JSON output, and validates it against a Pydantic schema.
    """
    # Enforce JSON formatting instructions in prompt
    json_instruction = (
        f"\n\nYou MUST return a JSON object that strictly adheres to the following JSON schema:\n"
        f"{schema.model_json_schema()}\n"
        f"Do not include any chat prefix or markdown wrappers like ```json. Return raw JSON only."
    )
    
    modified_system_prompt = system_prompt + json_instruction
    
    # Try up to 3 times to get valid JSON matching the schema
    for attempt in range(3):
        try:
            raw_content = await call_nemotron(
                system_prompt=modified_system_prompt,
                user_prompt=user_prompt,
                json_mode=True,
                model_id=model_id
            )
            # Remove possible markdown tags
            cleaned = raw_content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned.rsplit("\n", 1)[0]
            cleaned = cleaned.strip("`").strip()
            
            parsed_json = json.loads(cleaned)
            return schema.model_validate(parsed_json)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} to parse Nemotron JSON output failed: {e}")
            if attempt == 2:
                raise
