"""Structured logging and secret redaction."""

import json
import logging

from app.core.logging import JsonFormatter, redact_secrets


def test_json_formatter_emits_level_and_message() -> None:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert "timestamp" in payload


def test_redact_secrets_removes_configured_passwords() -> None:
    from app.core.config import get_settings

    settings = get_settings()
    raw = f"failed for {settings.postgres_password} and {settings.redis_password}"

    redacted = redact_secrets(raw)

    assert settings.postgres_password not in redacted
    assert settings.redis_password not in redacted
    assert redacted.count("***") == 2
