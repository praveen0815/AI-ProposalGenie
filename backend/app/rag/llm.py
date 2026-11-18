"""Answer generation. Retrieval does not import this module."""

from typing import Protocol

import httpx


class LanguageModelError(Exception):
    """The configured language model could not answer."""


class LanguageModel(Protocol):
    def answer(self, question: str, context: str) -> str:
        """Answer from the supplied context."""


_SYSTEM_PROMPT = (
    "You answer questions about one company using only the retrieved context. "
    "If the context does not contain enough evidence, say you do not have enough "
    "information in the company documents. Do not invent prices, policies, names, or commitments."
)


class OpenAICompatibleLanguageModel:
    """Chat-completions client for an OpenAI-compatible provider."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: float) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def answer(self, question: str, context: str) -> str:
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
                    ],
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            raise LanguageModelError("The language model request failed") from exc
        text = str(content).strip()
        if not text:
            raise LanguageModelError("The language model returned an empty answer")
        return text
