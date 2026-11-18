"""Assemble the drafted sections and reject a structure that fails validation."""

from typing import Any

from app.agents.errors import AgentOutputError
from app.agents.state import ProposalAgentState
from app.agents.tools import AgentTools


def finalize_proposal(state: ProposalAgentState, tools: AgentTools) -> dict[str, Any]:
    sections = [dict(section) for section in state["draft_sections"]]
    if state.get("review_limit_reached"):
        note = "Quality review reached its iteration limit. Review the findings before sending this proposal."
        for section in sections:
            section["needs_review"] = True
            existing = str(section.get("review_notes") or "").strip()
            section["review_notes"] = f"{existing} {note}".strip() if existing else note
    result = tools.validate_sections(sections)
    if not result.valid:
        raise AgentOutputError("The final proposal did not pass validation", "finalization")
    return {"draft_sections": sections, "execution_status": "completed"}
