"""Password hashing helpers (bcrypt via passlib)."""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pre-computed hash used to keep login timing constant when the email is unknown.
_DUMMY_HASH = pwd_context.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    """
    Hash a plaintext password with bcrypt.

    Args:
        password: Plaintext password

    Returns:
        The bcrypt hash string
    """
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str | None) -> bool:
    """
    Check a plaintext password against a stored hash.

    When ``hashed`` is None (e.g. OAuth-only account) a dummy hash is still
    verified so the response time does not reveal whether the account exists.

    Args:
        plain: Plaintext password supplied by the client
        hashed: Stored bcrypt hash, or None

    Returns:
        True if the password matches, otherwise False
    """
    if not hashed:
        pwd_context.verify(plain, _DUMMY_HASH)
        return False
    try:
        return pwd_context.verify(plain, hashed)
    except ValueError:
        return False
