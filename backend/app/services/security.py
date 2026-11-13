"""Password hashing and JWT access tokens."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings

_hasher = PasswordHash.recommended()
_dummy_hash: str | None = None


class TokenError(Exception):
    """The access token is missing, expired, or not signed by this application."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


def dummy_verify(password: str) -> None:
    """Spend a hash verification so unknown emails do not return faster."""

    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password("not-a-real-password")
    verify_password(password, _dummy_hash)


def create_access_token(*, user_id: UUID, token_version: int, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    lifetime = expires_delta if expires_delta is not None else timedelta(minutes=settings.access_token_expire_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> tuple[UUID, int]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = UUID(str(payload["sub"]))
        token_version = payload["ver"]
        if not isinstance(token_version, int):
            raise TokenError
    except (InvalidTokenError, KeyError, ValueError, TypeError) as exc:
        raise TokenError from exc
    return user_id, token_version
