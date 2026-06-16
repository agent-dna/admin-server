"""Password hashing helpers.

Uses bcrypt, which generates a per-password random salt and embeds it in the
returned hash string, so the single stored value is enough to verify later.
"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from config import settings

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of a plaintext password.

    Note: bcrypt only considers the first 72 bytes of the password.
    """
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if the plaintext password matches the stored bcrypt hash.

    Returns False (rather than raising) for malformed/empty stored hashes.
    """
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, *, did: str, org_id: str) -> str:
    """Create a signed JWT for the given subject (admin username).

    The admin's ``did`` and ``org_id`` are embedded as claims so downstream
    services can identify the admin from the token alone, without a lookup.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "did": did,
        "org_id": org_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token
