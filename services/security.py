import base64
import hashlib

from cryptography.fernet import Fernet

from config import settings


def _build_fernet() -> Fernet:
    if not settings.encryption_key.strip():
        raise ValueError("SESSION_ENCRYPTION_KEY must be set in .env")
    raw = settings.encryption_key.encode("utf-8")
    if len(raw) == 44 and raw.endswith(b"="):
        key = raw
    else:
        digest = hashlib.sha256(raw).digest()
        key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_session(value: str) -> str:
    return _build_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_session(value: str) -> str:
    return _build_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
