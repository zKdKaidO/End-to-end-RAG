from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings


_hasher = PasswordHasher(type=Type.ID)
_dummy_hash = _hasher.hash("dummy-auth-verification-passphrase")


class PasswordPolicyError(ValueError):
    pass


def validate_password(password: str) -> None:
    if not isinstance(password, str):
        raise PasswordPolicyError("Password must be a string")
    if len(password) < settings.AUTH_PASSWORD_MIN_LENGTH:
        raise PasswordPolicyError(f"Password must contain at least {settings.AUTH_PASSWORD_MIN_LENGTH} characters")
    if len(password) > settings.AUTH_PASSWORD_MAX_LENGTH:
        raise PasswordPolicyError(f"Password must contain at most {settings.AUTH_PASSWORD_MAX_LENGTH} characters")


def hash_password(password: str) -> str:
    validate_password(password)
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    if len(password) > settings.AUTH_PASSWORD_MAX_LENGTH:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_verify(password: str) -> None:
    try:
        _hasher.verify(_dummy_hash, password[: settings.AUTH_PASSWORD_MAX_LENGTH])
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        pass
