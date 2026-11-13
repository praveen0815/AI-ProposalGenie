"""Settings construction without a live database."""

import pytest
from pydantic import ValidationError

from app.core.config import PROJECT_ROOT, Settings


def test_database_uri_encodes_credentials() -> None:
    settings = Settings(
        postgres_user="proposal genie",
        postgres_password="p@ss word",
        postgres_db="proposalgenie",
        redis_password="redis secret",
        database_url=None,
        redis_url=None,
    )

    assert settings.sqlalchemy_database_uri == (
        "postgresql+psycopg://proposal+genie:p%40ss+word@localhost:5432/proposalgenie"
    )
    assert settings.redis_dsn == "redis://:redis+secret@localhost:6379/0"


def test_explicit_urls_override_parts() -> None:
    settings = Settings(
        postgres_user="user",
        postgres_password="password",
        postgres_db="db",
        redis_password="secret",
        database_url="postgresql+psycopg://elsewhere/db",
        redis_url="redis://:secret@cache:6379/1",
    )

    assert settings.sqlalchemy_database_uri == "postgresql+psycopg://elsewhere/db"
    assert settings.redis_dsn == "redis://:secret@cache:6379/1"


def test_cors_origins_accept_json_and_commas() -> None:
    from_json = Settings(
        postgres_user="user",
        postgres_password="password",
        postgres_db="db",
        redis_password="secret",
        cors_origins='["https://app.example.test","https://admin.example.test"]',
    )
    from_commas = Settings(
        postgres_user="user",
        postgres_password="password",
        postgres_db="db",
        redis_password="secret",
        cors_origins="https://app.example.test, https://admin.example.test",
    )

    expected = ["https://app.example.test", "https://admin.example.test"]
    assert from_json.cors_origins == expected
    assert from_commas.cors_origins == expected


def test_document_storage_cannot_live_in_the_frontend() -> None:
    with pytest.raises(ValidationError):
        Settings(
            postgres_user="user",
            postgres_password="password",
            postgres_db="db",
            redis_password="secret",
            jwt_secret="x" * 32,
            document_storage_path=str(PROJECT_ROOT / "frontend" / "public" / "uploads"),
        )
