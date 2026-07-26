"""Encrypt/decrypt provider API keys at rest using a key derived from APP_SECRET."""

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.core.config import settings

_PREFIX = "enc:v1:"

_derived_key: bytes | None = None


def _get_fernet() -> Fernet:
    global _derived_key
    secret = settings.app_secret
    if not secret or len(secret) < 32:
        raise ValueError("APP_SECRET must be set and at least 32 characters")
    if _derived_key is None:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"app-settings-key-v1",
        )
        raw_key = hkdf.derive(secret.encode())
        _derived_key = base64.urlsafe_b64encode(raw_key)
    return Fernet(_derived_key)


def encrypt_secret(plain: str | None) -> str | None:
    """Encrypt a provider API key for storage. None/empty pass through unchanged."""
    if not plain:
        return plain
    fernet = _get_fernet()
    token = fernet.encrypt(plain.encode()).decode()
    return f"{_PREFIX}{token}"


def decrypt_secret(stored: str | None) -> str | None:
    """Decrypt a stored provider API key. None/empty pass through unchanged.

    Values without the "enc:v1:" prefix are legacy plaintext written before
    encryption existed; they are returned as-is so no Alembic data migration
    is required to backfill them.
    """
    if not stored:
        return stored
    if not stored.startswith(_PREFIX):
        return stored
    fernet = _get_fernet()
    token = stored[len(_PREFIX):]
    return fernet.decrypt(token.encode()).decode()
