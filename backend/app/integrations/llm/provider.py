"""The generation interface used by proposal services."""

from typing import Any, Protocol

from app.integrations.llm.types import Completion


class StructuredLanguageModel(Protocol):
    model_name: str

    def generate_json(self, *, purpose: str, prompt: str, schema: dict[str, Any]) -> Completion:
        """Return JSON text that follows the supplied schema."""
