"""LangGraph proposal workflow, persistence, and company isolation."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.graph import AgentContext, build_graph
from app.agents.tools import ClientResult, WorkflowTools
from app.api.deps import get_proposal_model
from app.main import app
from app.models.agent import AgentRun
from app.models.enums import AgentRunStatus
from app.models.proposal import Proposal
from tests.agent_fakes import FakeAgentModel

PASSWORD = "Correct-horse-1"


def _auth(api: TestClient, prefix: str) -> dict[str, str]:
    response = api.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:10]}@example.com", "password": PASSWORD, "full_name": prefix.title()},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _company(api: TestClient, headers: dict[str, str]) -> str:
    response = api.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Northwind", "industry": "Software", "description": "We deliver software projects for business clients."},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _proposal(api: TestClient, headers: dict[str, str], company_id: str) -> dict:
    response = api.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "company_id": company_id,
            "client_name": "Northwind Labs",
            "client_requirements": "Replace the checkout flow and keep the current catalog.",
            "project_title": "Checkout modernization",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _state() -> dict:
    return {
        "proposal_id": "proposal",
        "company_id": "company",
        "client_requirements": "Replace the checkout flow.",
        "generation_input": {"project_title": "Checkout", "client_requirements": "Replace the checkout flow."},
        "company_profile": {"name": "Northwind", "industry": "Software"},
        "client": {"name": "Northwind Labs"},
        "requirement_summary": {},
        "retrieved_context": [],
        "retrieval_status": "empty",
        "research_findings": [],
        "research_sources": [],
        "external_research_status": "not_configured",
        "solution": {},
        "draft_sections": [],
        "review": {},
        "iteration": 0,
        "max_iterations": 2,
        "execution_status": "running",
        "resume_node": "",
        "current_node": "",
        "error": "",
        "review_limit_reached": False,
    }


def _tools(model: FakeAgentModel) -> WorkflowTools:
    return WorkflowTools(
        company_id="company",
        client=ClientResult(name="Northwind Labs", industry="Retail"),
        model=model,
        retrieve_knowledge=lambda _query: [],
        research_api_key="",
        research_base_url="",
    )


def test_graph_revises_once_and_does_not_invent_external_research() -> None:
    model = FakeAgentModel(reviews=[False, True])
    graph = build_graph(AgentContext(model=model, tools=_tools(model), on_node=lambda *_args: None))

    result = graph.invoke(_state())

    assert result["execution_status"] == "completed"
    assert result["review"]["approved"] is True
    assert result["external_research_status"] == "not_configured"
    assert result["research_sources"] == []
    assert "https://example.invalid/invented" not in str(result["research_findings"])
    assert model.calls.count("agent_sections") == 2
    assert model.calls.count("agent_review") == 2
    assert len(result["draft_sections"]) == 10
    assert result["draft_sections"][0]["source_references"] == []


def test_graph_stops_at_the_review_limit() -> None:
    model = FakeAgentModel(reviews=[False, False, False])
    graph = build_graph(AgentContext(model=model, tools=_tools(model), on_node=lambda *_args: None))

    result = graph.invoke(_state())

    assert result["review_limit_reached"] is True
    assert result["execution_status"] == "completed"
    assert model.calls.count("agent_review") == 2
    assert model.calls.count("agent_sections") == 2


def test_successful_workflow_is_persisted(api: TestClient, db_session: Session) -> None:
    model = FakeAgentModel()
    app.dependency_overrides[get_proposal_model] = lambda: model
    owner = _auth(api, "owner")
    company_id = _company(api, owner)
    created = _proposal(api, owner, company_id)

    response = api.post(f"/api/v1/agents/proposals/{created['id']}/run", headers=owner)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "COMPLETED"
    assert [node["status"] for node in body["nodes"]] == ["completed"] * 6
    assert body["external_research_status"] == "not_configured"
    saved = api.get(f"/api/v1/proposals/{created['id']}", headers=owner)
    assert saved.status_code == 200
    assert saved.json()["status"] == "REVIEW"
    assert len(saved.json()["sections"]) == 10
    history = api.get(f"/api/v1/agents/proposals/{created['id']}/history", headers=owner)
    assert history.status_code == 200
    assert {event["node"] for event in history.json()} >= {
        "requirement_analysis",
        "research",
        "solution_architecture",
        "proposal_writer",
        "quality_review",
        "finalization",
    }
    db_session.expire_all()
    stored = db_session.get(Proposal, created["id"])
    assert stored is not None
    assert stored.generation_metadata["workflow"] == "langgraph"
    assert db_session.scalar(select(func.count()).select_from(Proposal).where(Proposal.company_id == UUID(company_id))) == 1


def test_invalid_output_and_model_failure_are_recorded(api: TestClient) -> None:
    owner = _auth(api, "owner")
    company_id = _company(api, owner)
    invalid_model = FakeAgentModel()
    invalid_model.invalid_purpose = "agent_requirements"
    app.dependency_overrides[get_proposal_model] = lambda: invalid_model
    invalid_proposal = _proposal(api, owner, company_id)

    invalid = api.post(f"/api/v1/agents/proposals/{invalid_proposal['id']}/run", headers=owner)

    assert invalid.status_code == 502
    invalid_status = api.get(f"/api/v1/agents/proposals/{invalid_proposal['id']}/status", headers=owner)
    assert invalid_status.json()["status"] == "FAILED"
    assert invalid_status.json()["nodes"][0]["status"] == "failed"

    failed_model = FakeAgentModel()
    failed_model.fail_purpose = "agent_solution"
    failed_model.fail_times = 1
    app.dependency_overrides[get_proposal_model] = lambda: failed_model
    failed_proposal = _proposal(api, owner, company_id)
    failed = api.post(f"/api/v1/agents/proposals/{failed_proposal['id']}/run", headers=owner)

    assert failed.status_code == 503
    failed_status = api.get(f"/api/v1/agents/proposals/{failed_proposal['id']}/status", headers=owner)
    assert failed_status.json()["current_node"] == "solution_architecture"
    assert failed_status.json()["nodes"][0]["status"] == "completed"
    assert failed_status.json()["nodes"][2]["status"] == "failed"


def test_resume_continues_the_same_proposal(api: TestClient, db_session: Session) -> None:
    model = FakeAgentModel()
    model.fail_purpose = "agent_research"
    model.fail_times = 1
    app.dependency_overrides[get_proposal_model] = lambda: model
    owner = _auth(api, "owner")
    company_id = _company(api, owner)
    created = _proposal(api, owner, company_id)

    failed = api.post(f"/api/v1/agents/proposals/{created['id']}/run", headers=owner)
    assert failed.status_code == 503
    run_id = api.get(f"/api/v1/agents/proposals/{created['id']}/status", headers=owner).json()["run_id"]

    resumed = api.post(f"/api/v1/agents/proposals/{created['id']}/resume", headers=owner)

    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == "COMPLETED"
    assert resumed.json()["run_id"] == run_id
    assert db_session.scalar(select(func.count()).select_from(Proposal).where(Proposal.company_id == UUID(company_id))) == 1


def test_a_running_workflow_cannot_be_started_twice(api: TestClient, db_session: Session) -> None:
    owner = _auth(api, "owner")
    company_id = _company(api, owner)
    created = _proposal(api, owner, company_id)
    db_session.add(
        AgentRun(
            proposal_id=UUID(created["id"]),
            company_id=UUID(company_id),
            status=AgentRunStatus.RUNNING,
            current_node="research",
            iteration=0,
            state={"proposal_id": created["id"]},
            started_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    response = api.post(f"/api/v1/agents/proposals/{created['id']}/run", headers=owner)

    assert response.status_code == 409
    assert db_session.scalar(select(func.count()).select_from(Proposal).where(Proposal.company_id == UUID(company_id))) == 1


def test_agent_status_is_company_scoped(api: TestClient) -> None:
    owner = _auth(api, "owner")
    outsider = _auth(api, "outsider")
    company_id = _company(api, owner)
    created = _proposal(api, owner, company_id)

    hidden = api.get(f"/api/v1/agents/proposals/{created['id']}/status", headers=outsider)
    visible = api.get(f"/api/v1/agents/proposals/{created['id']}/status", headers=owner)

    assert hidden.status_code == 404
    assert visible.status_code == 200
    assert visible.json()["status"] == "NOT_STARTED"
