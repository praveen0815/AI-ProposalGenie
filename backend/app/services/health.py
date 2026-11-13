"""Connectivity checks for PostgreSQL and Redis."""

import logging
import time
from datetime import datetime, timezone

from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.logging import redact_secrets
from app.db.session import get_engine
from app.schemas.health import DependencyCheck, HealthResponse

logger = logging.getLogger(__name__)


def _log_failure(dependency: str, exc: Exception) -> None:
    logger.error("%s connectivity check failed: %s", dependency, redact_secrets(f"{type(exc).__name__}: {exc}"))


def check_postgres() -> DependencyCheck:
    """Run SELECT 1 and report latency without returning connection details."""

    started = time.perf_counter()
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        elapsed_ms = (time.perf_counter() - started) * 1000
    except SQLAlchemyError as exc:
        _log_failure("postgresql", exc)
        return DependencyCheck(name="postgresql", status="down", detail=type(exc).__name__)
    return DependencyCheck(name="postgresql", status="up", latency_ms=round(elapsed_ms, 2))


def check_redis() -> DependencyCheck:
    """Ping Redis and report latency without returning the connection URL."""

    settings = get_settings()
    client: Redis | None = None
    started = time.perf_counter()
    try:
        client = Redis.from_url(
            settings.redis_dsn,
            socket_connect_timeout=2,
            socket_timeout=2,
            decode_responses=True,
        )
        pong = client.ping()
        elapsed_ms = (time.perf_counter() - started) * 1000
        if pong is not True and pong not in {b"PONG", "PONG"}:
            return DependencyCheck(name="redis", status="down", detail="PingFailed")
        return DependencyCheck(name="redis", status="up", latency_ms=round(elapsed_ms, 2))
    except Exception as exc:
        _log_failure("redis", exc)
        return DependencyCheck(name="redis", status="down", detail=type(exc).__name__)
    finally:
        if client is not None:
            client.close()


def collect_health() -> HealthResponse:
    """Combine application metadata with dependency checks."""

    settings = get_settings()
    checks = [check_postgres(), check_redis()]
    status = "ok" if all(check.status == "up" for check in checks) else "degraded"
    return HealthResponse(
        status=status,
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        checked_at=datetime.now(timezone.utc),
        checks=checks,
    )
