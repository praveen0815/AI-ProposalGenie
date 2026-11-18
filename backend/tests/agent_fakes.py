"""Deterministic model responses for the multi-agent workflow."""

import json

from app.integrations.llm.errors import LLMAPIError
from app.integrations.llm.types import Completion, TokenUsage
from app.proposals.sections import SECTION_SPECS


class FakeAgentModel:
    model_name = "fake-gemini"

    def __init__(self, reviews: list[bool] | None = None) -> None:
        self.calls: list[str] = []
        self.reviews = reviews or [True]
        self.invalid_purpose: str | None = None
        self.fail_purpose: str | None = None
        self.fail_times = 0
        self._review_index = 0

    def generate_json(self, *, purpose: str, prompt: str, schema: dict) -> Completion:
        self.calls.append(purpose)
        if purpose == self.fail_purpose and self.fail_times > 0:
            self.fail_times -= 1
            raise LLMAPIError("unavailable")
        if purpose == self.invalid_purpose:
            return Completion(text="not-json", model=self.model_name, usage=None)
        payload = self._payload(purpose)
        return Completion(
            text=json.dumps(payload),
            model=self.model_name,
            usage=TokenUsage(prompt_tokens=2, completion_tokens=2, total_tokens=4),
        )

    def _payload(self, purpose: str) -> dict:
        if purpose == "agent_requirements":
            return {
                "summary": "The client wants a checkout replacement.",
                "objectives": ["Replace checkout"],
                "constraints": ["Keep the current catalog"],
                "missing_information": ["Budget range was not provided"],
            }
        if purpose == "agent_research":
            return {
                "findings": [
                    {
                        "statement": "External research was claimed by the model.",
                        "evidence_type": "external",
                        "source_label": "Invented source",
                        "url": "https://example.invalid/invented",
                    }
                ]
            }
        if purpose == "agent_solution":
            return {
                "summary": "Deliver the checkout change in stages.",
                "components": ["Checkout service"],
                "stages": ["Discovery", "Delivery"],
                "deliverables": ["Updated checkout"],
                "dependencies": ["Catalog access"],
                "risks": ["Missing budget"],
            }
        if purpose == "agent_review":
            approved = self.reviews[min(self._review_index, len(self.reviews) - 1)]
            self._review_index += 1
            return {
                "approved": approved,
                "contradictions": [],
                "unsupported_claims": [],
                "unmet_requirements": [],
                "corrections": [] if approved else ["Remove unsupported claims and mark missing budget for review."],
            }
        sections = [
            {
                "key": key,
                "title": title,
                "body": "AI draft. Not provided — needs review.",
                "needs_review": False,
                "review_notes": "",
                "source_document_ids": ["00000000-0000-0000-0000-000000000099"],
            }
            for key, title in SECTION_SPECS
        ]
        return {"sections": sections}
