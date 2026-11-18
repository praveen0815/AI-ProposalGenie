"""FastAPI dependencies."""

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.user import User
from app.repositories import users as user_repository
from app.rag.embedding_service import SentenceTransformerEmbeddings
from app.integrations.llm.gemini import GeminiLanguageModel
from app.rag.llm import OpenAICompatibleLanguageModel
from app.rag.vector_store import ChromaVectorStore
from app.services.security import TokenError, decode_access_token
from app.storage.local import LocalDocumentStorage

_bearer = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a session and always close it."""

    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Load the user for a valid access token."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        user_id, token_version = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc

    user = user_repository.get_by_id(db, user_id)
    if user is None or not user.is_active or user.token_version != token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


@lru_cache
def get_document_storage() -> LocalDocumentStorage:
    """Local storage rooted outside the frontend. Tests can override this dependency."""

    return LocalDocumentStorage(Path(get_settings().document_storage_path))


@lru_cache
def get_embedding_service() -> SentenceTransformerEmbeddings:
    return SentenceTransformerEmbeddings(get_settings().embedding_model)


@lru_cache
def get_vector_store() -> ChromaVectorStore:
    settings = get_settings()
    return ChromaVectorStore(Path(settings.chroma_path), settings.chroma_collection)


def get_language_model() -> OpenAICompatibleLanguageModel:
    settings = get_settings()
    if not settings.llm_api_key.strip():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No language model is configured")
    return OpenAICompatibleLanguageModel(
        settings.llm_base_url,
        settings.llm_api_key,
        settings.llm_model,
        settings.llm_timeout_seconds,
    )


def get_proposal_model() -> GeminiLanguageModel:
    """Gemini client for proposal generation. The key stays on the server."""

    settings = get_settings()
    if not settings.gemini_api_key.strip():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Gemini is not configured")
    return GeminiLanguageModel(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        base_url=settings.gemini_base_url,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_retries=settings.gemini_max_retries,
    )
