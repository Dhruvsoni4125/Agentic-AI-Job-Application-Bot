# app/services/storage.py
import logging
from supabase import create_client, Client
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

class SupabaseStorageException(Exception):
    pass

def upload_file(bucket_name: str, file_path_in_bucket: str, file_bytes: bytes, content_type: str = "application/pdf") -> str:
    """
    Synchronously uploads file bytes to a Supabase storage bucket.
    Returns the file path within the bucket if successful.
    """
    try:
        # Check if file exists, if yes we might need to overwrite
        # Standard supabase library upload uses:
        # supabase.storage.from_(bucket_name).upload(path, file, file_options)
        response = supabase.storage.from_(bucket_name).upload(
            path=file_path_in_bucket,
            file=file_bytes,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        # Note: Depending on supabase-py version, response might be a dict or object
        logger.info(f"Successfully uploaded file to {bucket_name}/{file_path_in_bucket}")
        return file_path_in_bucket
    except Exception as e:
        logger.error(f"Failed to upload file to Supabase Storage: {e}")
        raise SupabaseStorageException(f"Upload failed: {str(e)}")

def download_file(bucket_name: str, file_path_in_bucket: str) -> bytes:
    """
    Synchronously downloads file bytes from a Supabase storage bucket.
    """
    try:
        response = supabase.storage.from_(bucket_name).download(file_path_in_bucket)
        return response
    except Exception as e:
        logger.error(f"Failed to download file from Supabase Storage: {e}")
        raise SupabaseStorageException(f"Download failed: {str(e)}")

def get_signed_url(bucket_name: str, file_path_in_bucket: str, expires_in: int = 3600) -> str:
    """
    Generates a secure temporary public signed URL for a file in Supabase storage.
    """
    try:
        response = supabase.storage.from_(bucket_name).create_signed_url(file_path_in_bucket, expires_in)
        # response should contain a dictionary with "signedURL"
        if isinstance(response, dict) and "signedURL" in response:
            return response["signedURL"]
        elif hasattr(response, "get"):
            return response.get("signedURL", "")
        # fallback for different SDK response types
        elif hasattr(response, "signed_url"):
            return response.signed_url
        return str(response)
    except Exception as e:
        logger.error(f"Failed to generate signed URL for {file_path_in_bucket}: {e}")
        raise SupabaseStorageException(f"Failed to get signed URL: {str(e)}")
