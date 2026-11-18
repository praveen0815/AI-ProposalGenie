"""Typed state for the proposal workflow."""

from typing import Any, TypedDict

NODE_ORDER: tuple[str, ...] = (
    "requirement_analysis",
    "research",
    "solution_architecture",
    "proposal_writer",
    "quality_review",
    "finalization",
)

NODE_LABELS: dict[str, str] = {
    "requirement_analysis": "Requirement analysis",
    "research": "Research",
    "solution_architecture": "Solution design",
    "proposal_writer": "Writing",
    "quality_review": "Quality review",
    "finalization": "Finalization",
}


class ProposalAgentState(TypedDict):
    proposal_id: str
    company_id: str
    client_requirements: str
    generation_input: dict[str, Any]
    company_profile: dict[str, Any]
    client: dict[str, Any]
    requirement_summary: dict[str, Any]
    retrieved_context: list[dict[str, Any]]
    retrieval_status: str
    research_findings: list[dict[str, Any]]
    research_sources: list[dict[str, Any]]
    external_research_status: str
    solution: dict[str, Any]
    draft_sections: list[dict[str, Any]]
    review: dict[str, Any]
    iteration: int
    max_iterations: int
    execution_status: str
    resume_node: str
    current_node: str
    error: str
    review_limit_reached: bool
