"""Registration, login, and logout."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.repositories import users as user_repository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.security import create_access_token, dummy_verify, hash_password, verify_password


def _token_response(user: User) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user_id=user.id, token_version=user.token_version),
        expires_in=settings.access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


def register_user(db: Session, payload: RegisterRequest) -> TokenResponse:
    if user_repository.get_by_email(db, payload.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists",
        ) from exc
    db.refresh(user)
    return _token_response(user)


def login_user(db: Session, payload: LoginRequest) -> TokenResponse:
    user = user_repository.get_by_email(db, payload.email)
    if user is None or not user.is_active:
        dummy_verify(payload.password)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _token_response(user)


def logout_user(db: Session, user: User) -> None:
    user.token_version += 1
    user.updated_at = datetime.now(UTC)
    db.commit()
