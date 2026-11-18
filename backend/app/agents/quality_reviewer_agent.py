"""Review the draft and decide whether the writer must revise it."""

from typing import Any

from pydantic import BaseModel, Field

from app.agents.state import ProposalAgentState
from app.agents.tools import parse_json_object, validate_model
from app.integrations.llm.provider import StructuredLanguageModel

_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "approved": {"type": "BOOLEAN"},
        "contradictions": {"type": "ARRAY", "items": {"type": "STRING"}},
        "unsupported_claims": {"type": "ARRAY", "items": {"type": "STRING"}},
        "unmet_requirements": {"type": "ARRAY", "items": {"type": "STRING"}},
        "corrections": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["approved", "contradictions", "unsupported_claims", "unmet_requirements", "corrections"],
}


class ReviewResult(BaseModel):
    approved: bool
    contradictions: list[str] = Field(default_factory=list, max_length=12)
    unsupported_claims: list[str] = Field(default_factory=list, max_length=12)
    unmet_requirements: list[str] = Field(default_factory=list, max_length=12)
    corrections: list[str] = Field(default_factory=list, max_length=12)


def review_proposal(state: ProposalAgentState, model: StructuredLanguageModel) -> dict[str, Any]:
    prompt = (
        "You are the quality review agent. Check completeness, contradictions, consistency, "
        "unsupported claims, and whether the client requirements are addressed. "
        "Return actionable corrections. Approve only when no corrections remain.\n\n"
        f"Requirements: {state.get('requirement_summary', {})}\n"
        f"Client requirements: {state['client_requirements']}\n"
        f"Sections: {[{'title': section['title'], 'body': section['body']} for section in state['draft_sections']]}"
    )
    completion = model.generate_json(purpose="agent_review", prompt=prompt, schema=_SCHEMA)
    review = validate_model(ReviewResult, parse_json_object(completion.text, "quality_review"), "quality_review")
    approved = review.approved and not review.corrections and not review.unsupported_claims and not review.unmet_requirements
    iteration = state["iteration"] if approved else state["iteration"] + 1
    payload = review.model_dump()
    payload["approved"] = approved
    return {
        "review": payload,
        "iteration": iteration,
        "review_limit_reached": (not approved) and iteration >= state["max_iterations"],
    }
