"""Direct PostgreSQL and Redis connectivity checks."""

import pytest
from sqlalchemy import text

from app.api.deps import get_db
from app.services.health import check_postgres, check_redis


def test_postgres_check_is_up() -> None:
    result = check_postgres()

    assert result.status == "up"
    assert result.name == "postgresql"
    assert result.latency_ms is not None
    assert result.detail is None


def test_database_session_executes_select_one() -> None:
    generator = get_db()
    session = next(generator)
    try:
        value = session.execute(text("SELECT 1")).scalar_one()
    finally:
        generator.close()

    assert value == 1


def test_get_db_rolls_back_after_request_error() -> None:
    generator = get_db()
    session = next(generator)
    session.execute(text("SELECT 1"))
    assert session.in_transaction() is True

    with pytest.raises(RuntimeError, match="stop"):
        generator.throw(RuntimeError("stop"))

    assert session.in_transaction() is False


def test_redis_check_is_up() -> None:
    result = check_redis()

    assert result.status == "up"
    assert result.name == "redis"
    assert result.latency_ms is not None
    assert result.detail is None
