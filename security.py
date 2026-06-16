"""Password hashing helpers.

Uses bcrypt, which generates a per-password random salt and embeds it in the
returned hash string, so the single stored value is enough to verify later.
"""

import bcrypt


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash of a plaintext password.

    Note: bcrypt only considers the first 72 bytes of the password.
    """
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")
