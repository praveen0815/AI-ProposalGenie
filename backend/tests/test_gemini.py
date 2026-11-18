"""Gemini provider behavior with a mocked HTTP transport."""

import logging

import httpx
import pytest

from app.integrations.llm.errors import LLMAPIError, LLMResponseError, LLMTimeout
from app.integrations.llm.gemini import GeminiLanguageModel


def _model(handler, retries: int = 1) -> GeminiLanguageModel:
    return GeminiLanguageModel(
        api_key="secret-key",
        model="gemini-2.5-flash",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds=5,
        max_retries=retries,
        backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )


def test_gemini_retries_and_reports_token_usage(caplog: pytest.LogCaptureFixture) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert "secret-key" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "secret-key"
        if calls["count"] == 1:
            return httpx.Response(503, json={"error": {"message": "busy"}})
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": "{\"ok\": true}"}]}}],
                "usageMetadata": {"promptTokenCount": 2, "candidatesTokenCount": 3, "totalTokenCount": 5},
            },
        )

    caplog.set_level(logging.INFO)
    result = _model(handler).generate_json(purpose="proposal_outline", prompt="Write JSON", schema={"type": "OBJECT"})

    assert calls["count"] == 2
    assert result.text == "{\"ok\": true}"
    assert result.model == "gemini-2.5-flash"
    assert result.usage is not None
    assert result.usage.total_tokens == 5
    assert "secret-key" not in caplog.text


def test_gemini_timeout_is_bounded() -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        raise httpx.TimeoutException("timed out")

    with pytest.raises(LLMTimeout):
        _model(handler).generate_json(purpose="proposal_sections", prompt="Write JSON", schema={"type": "OBJECT"})

    assert calls["count"] == 2


def test_gemini_client_error_is_not_retried() -> None:
    calls = {"count": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(400, json={"error": {"message": "bad request"}})

    with pytest.raises(LLMAPIError):
        _model(handler).generate_json(purpose="proposal_sections", prompt="Write JSON", schema={"type": "OBJECT"})

    assert calls["count"] == 1


def test_gemini_rejects_an_empty_completion() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "  "}]}}]})

    with pytest.raises(LLMResponseError):
        _model(handler, retries=0).generate_json(purpose="proposal_sections", prompt="Write JSON", schema={"type": "OBJECT"})
