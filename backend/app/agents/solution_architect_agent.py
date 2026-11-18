"""Design a solution from the requirement summary and gathered evidence."""

from typing import Any

from pydantic import BaseModel, Field

from app.agents.state import ProposalAgentState
from app.agents.tools import parse_json_object, validate_model
from app.integrations.llm.provider import StructuredLanguageModel

_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "components": {"type": "ARRAY", "items": {"type": "STRING"}},
        "stages": {"type": "ARRAY", "items": {"type": "STRING"}},
        "deliverables": {"type": "ARRAY", "items": {"type": "STRING"}},
        "dependencies": {"type": "ARRAY", "items": {"type": "STRING"}},
        "risks": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["summary", "components", "stages", "deliverables", "dependencies", "risks"],
}


class SolutionPlan(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)
    components: list[str] = Field(max_length=12)
    stages: list[str] = Field(max_length=12)
    deliverables: list[str] = Field(max_length=12)
    dependencies: list[str] = Field(max_length=12)
    risks: list[str] = Field(max_length=12)


def design_solution(state: ProposalAgentState, model: StructuredLanguageModel) -> dict[str, Any]:
    prompt = (
        "You are the solution architect. Design components, stages, deliverables, dependencies, and risks. "
        "Use the requirement summary, company profile, and research findings. "
        "Do not invent certifications, case studies, client achievements, or prices.\n\n"
        f"Requirements: {state.get('requirement_summary', {})}\n"
        f"Research: {state['research_findings']}\n"
        f"Company profile: {state['company_profile']}\n"
        f"Request: {state['generation_input']}"
    )
    completion = model.generate_json(purpose="agent_solution", prompt=prompt, schema=_SCHEMA)
    plan = validate_model(SolutionPlan, parse_json_object(completion.text, "solution_architecture"), "solution_architecture")
    return {"solution": plan.model_dump()}
