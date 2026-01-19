"""
Encryption utilities for sensitive data (API hashes, auth keys)
"""
from cryptography.fernet import Fernet
from config import Config
import base64
import hashlib


def get_encryption_key():
    """
    Generate encryption key from app secret
    Uses SHA256 hash of SECRET_KEY to create Fernet-compatible key
    """
    secret = Config.SECRET_KEY.encode()
    key = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_api_hash(api_hash: str) -> str:
    """
    Encrypt API hash for storage
    
    Args:
        api_hash: Plain text API hash
        
    Returns:
        Encrypted string (base64)
    """
    if not api_hash:
        return ""
    
    f = Fernet(get_encryption_key())
    encrypted = f.encrypt(api_hash.encode())
    return encrypted.decode()


def decrypt_api_hash(encrypted: str) -> str:
    """
    Decrypt API hash for use
    
    Args:
        encrypted: Encrypted API hash (base64)
        
    Returns:
        Plain text API hash
    """
    if not encrypted:
        return ""
    
    f = Fernet(get_encryption_key())
    try:
        decrypted = f.decrypt(encrypted.encode())
        return decrypted.decode()
    except Exception:
        # Fallback: return original string if decryption fails (assuming it's plain text)
        return encrypted


def encrypt_auth_key(auth_key: bytes) -> bytes:
    """
    Encrypt auth key for storage
    
    Args:
        auth_key: Raw auth key bytes
        
    Returns:
        Encrypted bytes
    """
    if not auth_key:
        return b""
    
    f = Fernet(get_encryption_key())
    return f.encrypt(auth_key)


def decrypt_auth_key(encrypted: bytes) -> bytes:
    """
    Decrypt auth key for use
    
    Args:
        encrypted: Encrypted auth key bytes
        
    Returns:
        Raw auth key bytes
    """
    if not encrypted:
        return b""
    
    f = Fernet(get_encryption_key())
    return f.decrypt(encrypted)
