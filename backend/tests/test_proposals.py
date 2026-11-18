"""Proposal generation, persistence, and company isolation."""

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_proposal_model, get_vector_store
from app.main import app
from app.models.proposal import Proposal, ProposalVersion
from tests.proposal_fakes import FakeProposalModel

PASSWORD = "Correct-horse-1"


def _auth(api: TestClient, prefix: str) -> dict[str, str]:
    response = api.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:10]}@example.com", "password": PASSWORD, "full_name": prefix.title()},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}", "email": body["user"]["email"]}


def _company(api: TestClient, headers: dict[str, str], name: str, *, profile: bool = True) -> str:
    payload: dict[str, object] = {"name": name}
    if profile:
        payload["industry"] = "Software"
        payload["description"] = "We deliver software projects for business clients."
    response = api.post("/api/v1/companies", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _payload(company_id: str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "company_id": company_id,
        "client_name": "Northwind Labs",
        "client_industry": "Retail",
        "client_requirements": "Replace the checkout flow and keep the current catalog.",
        "project_title": "Checkout modernization",
        "project_description": "A staged replacement of checkout.",
    }
    body.update(overrides)
    return body


def _create(api: TestClient, headers: dict[str, str], company_id: str, **overrides: object) -> dict:
    response = api.post("/api/v1/proposals", headers=headers, json=_payload(company_id, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_generate_saves_sections_without_inventing_a_budget(
    api: TestClient, db_session: Session, proposal_model: FakeProposalModel
) -> None:
    owner = _auth(api, "owner")
    company_id = _company(api, owner, "Northwind")
    created = _create(api, owner, company_id, timeline="6 weeks")

    generated = api.post(f"/api/v1/proposals/{created['id']}/generate", headers=owner)

    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["status"] == "REVIEW"
    assert body["model_name"] == "fake-gemini"
    assert body["prompt_version"] == "proposal-v1"
    assert body["retrieval_status"] == "empty"
    assert body["token_usage"]["total_tokens"] == 20
    assert [section["title"] for section in body["sections"]] == [
        "Executive Summary",
        "Client Requirements",
        "Proposed Solution",
        "Scope of Work",
        "Deliverables",
        "Implementation Methodology",
        "Project Timeline",
        "Budget and Cost Breakdown",
        "Terms and Conditions",
        "Conclusion",
    ]
    assert all(section["body"].startswith("AI draft.") for section in body["sections"])
    budget = next(section for section in body["sections"] if section["title"] == "Budget and Cost Breakdown")
    timeline = next(section for section in body["sections"] if section["title"] == "Project Timeline")
    assert budget["needs_review"] is True
    assert "Budget range was not provided." in budget["review_notes"]
    assert timeline["needs_review"] is False
    assert proposal_model.calls == ["proposal_outline", "proposal_sections"]
    assert "api_key" not in generated.text

    db_session.expire_all()
    stored = db_session.get(Proposal, UUID(created["id"]))
    assert stored is not None
    assert stored.status.value == "REVIEW"
    assert len(stored.sections) == 10
    assert stored.generation_input["client_name"] == "Northwind Labs"
    versions = db_session.scalar(select(func.count()).select_from(ProposalVersion).where(ProposalVersion.proposal_id == stored.id))
    assert versions == 1


def test_invalid_proposal_input_is_rejected(api: TestClient) -> None:
    owner = _auth(api, "owner")
    company_id = _company(api, owner, "Northwind")

    response = api.post("/api/v1/proposals", headers=owner, json=_payload(company_id, client_name="  ", currency="US"))

    assert response.status_code == 422


def test_missing_company_profile_blocks_generation(api: TestClient) -> None:
    owner = _auth(api, "owner")
    company_id = _company(api, owner, "Bare Co", profile=False)
    created = _create(api, owner, company_id)

    response = api.post(f"/api/v1/proposals/{created['id']}/generate", headers=owner)

    assert response.status_code == 409
    assert "company profile" in response.json()["message"]


def test_generation_continues_when_retrieval_is_unavailable(api: TestClient, proposal_model: FakeProposalModel) -> None:
    class BrokenStore:
        def query(self, **_kwargs: object) -> list:
            raise RuntimeError("store unavailable")

    owner = _auth(api, "owner")
    company_id = _company(api, owner, "Northwind")
    created = _create(api, owner, company_id)
    app.dependency_overrides[get_vector_store] = lambda: BrokenStore()

    response = api.post(f"/api/v1/proposals/{created['id']}/generate", headers=owner)

    assert response.status_code == 200, response.text
    assert response.json()["retrieval_status"] == "unavailable"
    assert response.json()["source_references"] == []
    assert proposal_model.calls


def test_language_model_failures_are_reported(api: TestClient, proposal_model: FakeProposalModel) -> None:
    owner = _auth(api, "owner")
    company_id = _company(api, owner, "Northwind")
    created = _create(api, owner, company_id)

    proposal_model.failure = "timeout"
    timed_out = api.post(f"/api/v1/proposals/{created['id']}/generate", headers=owner)
    proposal_model.failure = "invalid"
    invalid = api.post(f"/api/v1/proposals/{created['id']}/generate", headers=owner)
    proposal_model.failure = "api"
    failed = api.post(f"/api/v1/proposals/{created['id']}/generate", headers=owner)

    assert timed_out.status_code == 503
    assert "timed out" in timed_out.json()["message"]
    assert invalid.status_code == 502
    assert "could not be validated" in invalid.json()["message"]
    assert failed.status_code == 503
    assert failed.json()["message"] == "The language model could not generate the proposal"
    saved = api.get(f"/api/v1/proposals/{created['id']}", headers=owner)
    assert saved.json()["status"] == "DRAFT"
    assert saved.json()["generation_error"]


def test_generation_requires_a_configured_provider(api: TestClient) -> None:
    owner = _auth(api, "owner")
    company_id = _company(api, owner, "Northwind")
    created = _create(api, owner, company_id)
    app.dependency_overrides.pop(get_proposal_model, None)

    response = api.post(f"/api/v1/proposals/{created['id']}/generate", headers=owner)

    assert response.status_code == 503
    assert response.json()["message"] == "Gemini is not configured"


def test_proposals_stay_inside_the_company(api: TestClient) -> None:
    owner = _auth(api, "owner")
    member = _auth(api, "member")
    outsider = _auth(api, "outsider")
    company_id = _company(api, owner, "Northwind")
    other_company = _company(api, outsider, "Contoso")
    added = api.post(
        f"/api/v1/companies/{company_id}/members",
        headers=owner,
        json={"email": member["email"], "role": "MEMBER"},
    )
    assert added.status_code == 201, added.text
    own = _create(api, owner, company_id)
    theirs = _create(api, outsider, other_company)

    listing = api.get("/api/v1/proposals", params={"company_id": company_id}, headers=owner)
    hidden_list = api.get("/api/v1/proposals", params={"company_id": company_id}, headers=outsider)
    visible = api.get(f"/api/v1/proposals/{own['id']}", headers=member)
    hidden = api.get(f"/api/v1/proposals/{own['id']}", headers=outsider)
    renamed = api.patch(
        f"/api/v1/proposals/{own['id']}",
        headers=owner,
        json={"title": "Renamed checkout", "status": "APPROVED"},
    )
    member_edit = api.patch(f"/api/v1/proposals/{own['id']}", headers=member, json={"title": "Member edit"})
    blocked = api.patch(f"/api/v1/proposals/{own['id']}", headers=owner, json={"status": "GENERATING"})
    denied = api.delete(f"/api/v1/proposals/{own['id']}", headers=member)
    removed = api.delete(f"/api/v1/proposals/{own['id']}", headers=owner)

    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [own["id"]]
    assert theirs["id"] not in {item["id"] for item in listing.json()}
    assert hidden_list.status_code == 404
    assert visible.status_code == 200
    assert hidden.status_code == 404
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed checkout"
    assert renamed.json()["status"] == "APPROVED"
    assert member_edit.status_code == 403
    assert blocked.status_code == 422
    assert denied.status_code == 403
    assert removed.status_code == 204


def test_retrieved_documents_are_stored_as_sources(api: TestClient) -> None:
    owner = _auth(api, "owner")
    company_id = _company(api, owner, "Northwind")
    evidence = "Northwind offers a fixed discovery workshop for retail checkout clients."
    upload = api.post(
        "/api/v1/knowledge/documents/upload",
        params={"company_id": company_id},
        headers=owner,
        files={"file": ("services.txt", evidence.encode(), "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    created = _create(
        api,
        owner,
        company_id,
        client_requirements=evidence,
        project_description=evidence,
        project_title="Discovery workshop",
    )

    generated = api.post(f"/api/v1/proposals/{created['id']}/generate", headers=owner)

    assert generated.status_code == 200, generated.text
    sources = generated.json()["source_references"]
    assert sources
    assert sources[0]["filename"] == "services.txt"
    assert generated.json()["sections"][0]["source_references"][0]["filename"] == "services.txt"
