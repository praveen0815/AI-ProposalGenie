"""Analyze the client request and record what is missing."""

from typing import Any

from pydantic import BaseModel, Field

from app.agents.state import ProposalAgentState
from app.agents.tools import AgentTools, parse_json_object, validate_model
from app.integrations.llm.provider import StructuredLanguageModel

_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "summary": {"type": "STRING"},
        "objectives": {"type": "ARRAY", "items": {"type": "STRING"}},
        "constraints": {"type": "ARRAY", "items": {"type": "STRING"}},
        "missing_information": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["summary", "objectives", "constraints", "missing_information"],
}


class RequirementSummary(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)
    objectives: list[str] = Field(max_length=12)
    constraints: list[str] = Field(max_length=12)
    missing_information: list[str] = Field(max_length=12)


def analyze_requirements(state: ProposalAgentState, model: StructuredLanguageModel, tools: AgentTools) -> dict[str, Any]:
    client = tools.client_info()
    prompt = (
        "You are the requirement analysis agent. Use only the client request and company profile. "
        "List objectives, constraints, and missing information. Do not invent facts that fill the gaps.\n\n"
        f"Client: {client.model_dump()}\n"
        f"Company profile: {state['company_profile']}\n"
        f"Request: {state['generation_input']}"
    )
    completion = model.generate_json(purpose="agent_requirements", prompt=prompt, schema=_SCHEMA)
    summary = validate_model(RequirementSummary, parse_json_object(completion.text, "requirement_analysis"), "requirement_analysis")
    return {"requirement_summary": summary.model_dump()}
