"""Google Gemini generateContent client."""

import logging
import time
from typing import Any

import httpx

from app.integrations.llm.errors import LLMAPIError, LLMResponseError, LLMTimeout
from app.integrations.llm.types import Completion, TokenUsage

logger = logging.getLogger("app.llm")

_RETRYABLE = {429, 500, 502, 503, 504}


class GeminiLanguageModel:
    """Calls Gemini with a timeout and a bounded retry. The API key is a request header."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
        backoff_seconds: float = 0.5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model_name = model
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._transport = transport

    def generate_json(self, *, purpose: str, prompt: str, schema: dict[str, Any]) -> Completion:
        url = f"{self._base_url}/models/{self.model_name}:generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        attempts = self._max_retries + 1
        last_status: int | None = None
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                response = self._post(url, payload)
            except httpx.TimeoutException as exc:
                self._log(purpose, attempt, "timeout", started, None)
                if attempt == attempts:
                    raise LLMTimeout("The language model timed out") from exc
                self._pause(attempt)
                continue
            except httpx.HTTPError as exc:
                self._log(purpose, attempt, "transport_error", started, None)
                if attempt == attempts:
                    raise LLMAPIError("The language model request failed") from exc
                self._pause(attempt)
                continue

            elapsed_status = response.status_code
            self._log(purpose, attempt, "response", started, elapsed_status)
            if response.status_code in _RETRYABLE and attempt < attempts:
                last_status = response.status_code
                self._pause(attempt)
                continue
            if response.status_code >= 400:
                last_status = response.status_code
                raise LLMAPIError(f"The language model returned status {last_status}")
            return self._completion(response)

        raise LLMAPIError(f"The language model returned status {last_status}")

    def _post(self, url: str, payload: dict[str, Any]) -> httpx.Response:
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            return client.post(url, headers={"x-goog-api-key": self._api_key}, json=payload)

    def _pause(self, attempt: int) -> None:
        delay = min(self._backoff * (2 ** (attempt - 1)), 2)
        if delay > 0:
            time.sleep(delay)

    def _log(self, purpose: str, attempt: int, outcome: str, started: float, status_code: int | None) -> None:
        logger.info(
            "gemini purpose=%s model=%s attempt=%s outcome=%s status=%s latency_ms=%s",
            purpose,
            self.model_name,
            attempt,
            outcome,
            status_code,
            int((time.perf_counter() - started) * 1000),
        )

    def _completion(self, response: httpx.Response) -> Completion:
        try:
            body = response.json()
            text = body["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError("The language model returned an unreadable response") from exc
        content = str(text).strip()
        if not content:
            raise LLMResponseError("The language model returned an empty response")
        usage_body = body.get("usageMetadata") or {}
        usage = TokenUsage(
            prompt_tokens=_optional_int(usage_body.get("promptTokenCount")),
            completion_tokens=_optional_int(usage_body.get("candidatesTokenCount")),
            total_tokens=_optional_int(usage_body.get("totalTokenCount")),
        )
        logger.info(
            "gemini usage model=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
            self.model_name,
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
        )
        return Completion(text=content, model=self.model_name, usage=usage)


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
