"""LangGraph orchestration for the proposal agents."""

from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.errors import AgentWorkflowError
from app.agents.finalization_agent import finalize_proposal
from app.agents.proposal_writer_agent import write_proposal
from app.agents.quality_reviewer_agent import review_proposal
from app.agents.requirement_agent import analyze_requirements
from app.agents.research_agent import research_context
from app.agents.solution_architect_agent import design_solution
from app.agents.state import NODE_ORDER, ProposalAgentState
from app.agents.tools import AgentTools
from app.integrations.llm.errors import LLMError
from app.integrations.llm.provider import StructuredLanguageModel


@dataclass
class AgentContext:
    model: StructuredLanguageModel
    tools: AgentTools
    on_node: Any


def route_entry(state: ProposalAgentState) -> str:
    node = state.get("resume_node") or "requirement_analysis"
    if node not in NODE_ORDER:
        return "requirement_analysis"
    return node


def route_review(state: ProposalAgentState) -> str:
    review = state.get("review") or {}
    if review.get("approved") or int(state.get("iteration") or 0) >= int(state.get("max_iterations") or 1):
        return "finalization"
    return "proposal_writer"


def build_graph(ctx: AgentContext):
    """Compile the fixed workflow. Agents run only through these transitions."""

    def step(name: str, function):
        def run(state: ProposalAgentState) -> dict[str, Any]:
            ctx.on_node(name, "started", state)
            try:
                update = function(state)
            except AgentWorkflowError:
                raise
            except LLMError as exc:
                raise AgentWorkflowError("The language model could not complete this step", name) from exc
            except Exception as exc:
                raise AgentWorkflowError("This step could not be completed", name) from exc
            update["current_node"] = name
            update["resume_node"] = ""
            ctx.on_node(name, "completed", {**state, **update})
            return update

        return run

    graph = StateGraph(ProposalAgentState)
    graph.add_node("requirement_analysis", step("requirement_analysis", lambda state: analyze_requirements(state, ctx.model, ctx.tools)))
    graph.add_node("research", step("research", lambda state: research_context(state, ctx.model, ctx.tools)))
    graph.add_node("solution_architecture", step("solution_architecture", lambda state: design_solution(state, ctx.model)))
    graph.add_node("proposal_writer", step("proposal_writer", lambda state: write_proposal(state, ctx.tools)))
    graph.add_node("quality_review", step("quality_review", lambda state: review_proposal(state, ctx.model)))
    graph.add_node("finalization", step("finalization", lambda state: finalize_proposal(state, ctx.tools)))
    graph.add_conditional_edges(START, route_entry, {name: name for name in NODE_ORDER})
    graph.add_edge("requirement_analysis", "research")
    graph.add_edge("research", "solution_architecture")
    graph.add_edge("solution_architecture", "proposal_writer")
    graph.add_edge("proposal_writer", "quality_review")
    graph.add_conditional_edges(
        "quality_review",
        route_review,
        {"proposal_writer": "proposal_writer", "finalization": "finalization"},
    )
    graph.add_edge("finalization", END)
    return graph.compile()
