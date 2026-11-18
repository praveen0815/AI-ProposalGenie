"""Write the proposal sections from approved context and review feedback."""

from typing import Any

from app.agents.state import ProposalAgentState
from app.agents.tools import AgentTools
from app.proposals.sections import SECTION_SPECS

_MISSING = {
    "project_timeline": "timeline",
    "scope_of_work": "scope_of_work",
    "deliverables": "deliverables",
    "terms_and_conditions": "payment_terms",
}
_NOTES = {
    "budget_and_cost": "Budget range was not provided.",
    "project_timeline": "Timeline was not provided.",
    "scope_of_work": "Scope of work was not provided.",
    "deliverables": "Deliverables were not provided.",
    "terms_and_conditions": "Payment terms were not provided.",
}


def write_proposal(state: ProposalAgentState, tools: AgentTools) -> dict[str, Any]:
    iteration = state["iteration"]
    review = state.get("review") or {}
    feedback = ""
    if review and not review.get("approved"):
        feedback = (
            "Apply these review corrections without adding unsupported claims:\n"
            f"{review.get('corrections', [])}\n"
            f"Unsupported claims to remove: {review.get('unsupported_claims', [])}\n"
        )
    allowed = {str(item["document_id"]) for item in state["retrieved_context"]}
    filenames = {str(item["document_id"]): item["filename"] for item in state["retrieved_context"]}
    indexes = {str(item["document_id"]): item.get("chunk_index") for item in state["retrieved_context"]}
    prompt = (
        "You are the proposal writer. Write every required section in order. "
        "Begin each body with 'AI draft.' Use company documents and the solution as evidence. "
        "When information is missing, write 'Not provided — needs review.' "
        "Do not invent experience, case studies, certifications, or financial figures.\n\n"
        f"{feedback}"
        f"Requirements: {state.get('requirement_summary', {})}\n"
        f"Solution: {state['solution']}\n"
        f"Research findings: {state['research_findings']}\n"
        f"Retrieved documents: {state['retrieved_context']}\n"
        f"Request: {state['generation_input']}\n"
        f"Sections: {list(SECTION_SPECS)}"
    )
    sections = tools.generate_sections(prompt=prompt, allowed_document_ids=allowed)
    provided = state["generation_input"]
    for section in sections:
        key = str(section["key"])
        notes = str(section["review_notes"] or "")
        if key == "budget_and_cost" or (key in _MISSING and not provided.get(_MISSING[key])):
            section["needs_review"] = True
            note = _NOTES[key]
            if key == "budget_and_cost" and provided.get("budget_range"):
                note = "Only the stated budget range is verified. A detailed cost breakdown was not provided."
            section["review_notes"] = f"{notes} {note}".strip() if notes else note
        section["source_references"] = [
            {"document_id": document_id, "filename": filenames[document_id], "chunk_index": indexes.get(document_id)}
            for document_id in section["source_document_ids"]
        ]
    return {"draft_sections": sections, "iteration": iteration}
