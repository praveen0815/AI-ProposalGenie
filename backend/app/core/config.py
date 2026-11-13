"""Environment-backed application settings."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


def _env_file() -> str | None:
    for candidate in (PROJECT_ROOT / ".env", BACKEND_DIR / ".env"):
        if candidate.is_file():
            return str(candidate)
    return None


class Settings(BaseSettings):
    """Runtime configuration.

    Credentials are required environment values. They have no defaults in code.
    """

    model_config = SettingsConfigDict(
        env_file=_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "ProposalGenie"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str
    postgres_password: str
    postgres_db: str
    database_url: str | None = None

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str
    redis_db: int = 0
    redis_url: str | None = None

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, ge=5, le=1440)

    document_storage_path: str = str(PROJECT_ROOT / "storage" / "documents")
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1, le=50 * 1024 * 1024)
    max_documents_per_company: int = Field(default=100, ge=1, le=10_000)

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                parsed = json.loads(stripped)
                if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                    raise ValueError("CORS_ORIGINS must be a JSON list of strings")
                return parsed
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("jwt_secret")
    @classmethod
    def jwt_secret_is_long_enough(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return stripped

    @field_validator("document_storage_path")
    @classmethod
    def document_storage_stays_private(cls, value: str) -> str:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        resolved = path.resolve()
        frontend = (PROJECT_ROOT / "frontend").resolve()
        if resolved.is_relative_to(frontend):
            raise ValueError("Document storage must stay outside the frontend")
        return str(resolved)

    @field_validator("jwt_algorithm")
    @classmethod
    def jwt_algorithm_is_hmac(cls, value: str) -> str:
        if value != "HS256":
            raise ValueError("Only HS256 access tokens are supported")
        return value

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_dsn(self) -> str:
        if self.redis_url:
            return self.redis_url
        password = quote_plus(self.redis_password)
        return f"redis://:{password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
