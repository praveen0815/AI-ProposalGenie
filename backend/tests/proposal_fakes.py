"""A stand-in Gemini client for proposal tests."""

import json
import re

from app.integrations.llm.errors import LLMAPIError, LLMTimeout
from app.integrations.llm.types import Completion, TokenUsage
from app.proposals.sections import SECTION_SPECS

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


class FakeProposalModel:
    model_name = "fake-gemini"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.failure: str | None = None

    def generate_json(self, *, purpose: str, prompt: str, schema: dict) -> Completion:
        self.calls.append(purpose)
        if self.failure == "timeout":
            raise LLMTimeout("timed out")
        if self.failure == "api":
            raise LLMAPIError("unavailable")
        if self.failure == "invalid":
            return Completion(text="not-json", model=self.model_name, usage=None)
        if purpose == "proposal_outline":
            sections = [
                {"key": key, "title": title, "objective": "Draft from verified context."} for key, title in SECTION_SPECS
            ]
        else:
            document_ids = _UUID.findall(prompt)
            sections = [
                {
                    "key": key,
                    "title": title,
                    "body": "AI draft. Not provided — needs review.",
                    "needs_review": False,
                    "review_notes": "",
                    "source_document_ids": document_ids if index == 0 else [],
                }
                for index, (key, title) in enumerate(SECTION_SPECS)
            ]
        return Completion(
            text=json.dumps({"sections": sections}),
            model=self.model_name,
            usage=TokenUsage(prompt_tokens=4, completion_tokens=6, total_tokens=10),
        )
