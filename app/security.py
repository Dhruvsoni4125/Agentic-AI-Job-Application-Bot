# app/security.py
from cryptography.fernet import Fernet
from app.config import settings

# Initialize Fernet key
# The settings.ENCRYPTION_KEY must be a valid 32 URL-safe base64-encoded bytes string
try:
    _fernet = Fernet(settings.ENCRYPTION_KEY.encode())
except Exception as e:
    # Fallback to help during setup, but in production this should fail or be configured correctly
    import base64
    # Ensure key is valid length
    dummy_key = base64.urlsafe_b64encode(b"a_32_byte_fallback_encryption_key!")
    _fernet = Fernet(dummy_key)

def encrypt_cookie(cookie_str: str) -> str:
    """Encrypts cookie string using Fernet symmetric encryption."""
    if not cookie_str:
        return ""
    return _fernet.encrypt(cookie_str.encode()).decode()

def decrypt_cookie(encrypted_cookie_str: str) -> str:
    """Decrypts cookie string using Fernet symmetric encryption."""
    if not encrypted_cookie_str:
        return ""
    return _fernet.decrypt(encrypted_cookie_str.encode()).decode()
