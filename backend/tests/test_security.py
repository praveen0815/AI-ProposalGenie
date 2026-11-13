"""Password hashing and token lifetime."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.services.security import TokenError, create_access_token, decode_access_token, hash_password, verify_password


def test_password_hash_is_not_plaintext() -> None:
    password = "Correct-horse-1"
    hashed = hash_password(password)

    assert hashed != password
    assert password not in hashed
    assert hashed.startswith("$argon2")
    assert verify_password(password, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_expired_token_is_rejected() -> None:
    token = create_access_token(user_id=uuid4(), token_version=1, expires_delta=timedelta(seconds=-1))

    with pytest.raises(TokenError):
        decode_access_token(token)


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(user_id=uuid4(), token_version=1)
    tampered = token[:-2] + ("a" if token[-2] != "a" else "b") + token[-1]

    with pytest.raises(TokenError):
        decode_access_token(tampered)


def test_token_round_trip_keeps_version() -> None:
    user_id = uuid4()
    token = create_access_token(user_id=user_id, token_version=3)

    decoded_id, version = decode_access_token(token)

    assert decoded_id == user_id
    assert version == 3
