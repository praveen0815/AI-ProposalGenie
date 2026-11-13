"""Structured JSON logging."""

import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus

from app.core.config import get_settings


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def redact_secrets(text: str) -> str:
    """Remove configured secrets from a log or error string."""

    settings = get_settings()
    secrets = (
        settings.postgres_password,
        settings.redis_password,
        settings.jwt_secret,
        quote_plus(settings.postgres_password),
        quote_plus(settings.redis_password),
    )
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***")
    return redacted


def configure_logging(level_name: str) -> None:
    """Send application logs to stdout as JSON."""

    level = getattr(logging, level_name.upper(), None)
    if not isinstance(level, int):
        level = logging.INFO

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True

    for name in ("httpx", "httpcore", "asyncio"):
        logging.getLogger(name).setLevel(logging.WARNING)
