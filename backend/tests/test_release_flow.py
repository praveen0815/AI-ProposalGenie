"""One company walks the product path with mocked Gemini and mocked research."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_proposal_model
from app.main import app
from tests.agent_fakes import FakeAgentModel

PASSWORD = "Correct-horse-1"


def test_mocked_release_flow_covers_the_product_path(api: TestClient) -> None:
    registered = api.post(
        "/api/v1/auth/register",
        json={"email": f"release-{uuid4().hex[:10]}@example.com", "password": PASSWORD, "full_name": "Release Owner"},
    )
    assert registered.status_code == 201, registered.text
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    company = api.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Northwind", "industry": "Software", "description": "We deliver checkout software."},
    )
    assert company.status_code == 201, company.text
    company_id = company.json()["id"]
    uploaded = api.post(
        "/api/v1/knowledge/documents/upload",
        headers=headers,
        params={"company_id": company_id},
        files={"file": ("checkout-notes.txt", b"The company delivers checkout software for retail clients.", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["processing_status"] == "COMPLETED"
    answer = api.post(
        "/api/v1/rag/query",
        headers=headers,
        json={"company_id": company_id, "question": "What checkout software does the company deliver?"},
    )
    assert answer.status_code == 200, answer.text
    proposal = api.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "company_id": company_id,
            "client_name": "Northwind Labs",
            "client_requirements": "Replace checkout.",
            "project_title": "Checkout modernization",
        },
    )
    assert proposal.status_code == 201, proposal.text
    proposal_id = proposal.json()["id"]
    generated = api.post(f"/api/v1/proposals/{proposal_id}/generate", headers=headers)
    assert generated.status_code == 200, generated.text
    assert generated.json()["sections"]

    app.dependency_overrides[get_proposal_model] = lambda: FakeAgentModel()
    workflow = api.post(f"/api/v1/agents/proposals/{proposal_id}/run", headers=headers)
    assert workflow.status_code == 200, workflow.text
    assert workflow.json()["status"] == "COMPLETED"

    current = api.get(f"/api/v1/proposals/{proposal_id}", headers=headers).json()
    edited = api.put(
        f"/api/v1/proposals/{proposal_id}/draft",
        headers=headers,
        json={
            "title": "Checkout modernization",
            "expected_revision": current["content_revision"],
            "sections": [
                {"id": current["sections"][0]["id"], "title": current["sections"][0]["title"], "body": "Edited by the owner."},
                *[
                    {"id": section["id"], "title": section["title"], "body": section["body"]}
                    for section in current["sections"][1:]
                ],
            ],
        },
    )
    assert edited.status_code == 200, edited.text
    version = api.post(
        f"/api/v1/proposals/{proposal_id}/versions",
        headers=headers,
        json={"change_description": "Owner edit"},
    )
    assert version.status_code == 201, version.text
    restored = api.post(f"/api/v1/proposals/{proposal_id}/versions/{version.json()['id']}/restore", headers=headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["sections"][0]["body"] == "Edited by the owner."
    costs = api.put(
        f"/api/v1/proposals/{proposal_id}/costs",
        headers=headers,
        json={
            "currency": "USD",
            "lines": [
                {
                    "name": "Consultant",
                    "category": "Labor",
                    "quantity": "2",
                    "unit": "person",
                    "unit_price": "100",
                    "duration": "3",
                    "tax_percent": "10",
                    "discount_percent": "5",
                    "source": "CONFIRMED",
                }
            ],
        },
    )
    assert costs.status_code == 200, costs.text
    assert costs.json()["grand_total"] == "627.00"
    current_status = api.get(f"/api/v1/proposals/{proposal_id}", headers=headers).json()["status"]
    if current_status == "DRAFT":
        submitted = api.post(f"/api/v1/proposals/{proposal_id}/approval", headers=headers, json={"action": "SUBMIT"})
        assert submitted.status_code == 200, submitted.text
    approved = api.post(f"/api/v1/proposals/{proposal_id}/approval", headers=headers, json={"action": "APPROVE"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    pdf = api.post(f"/api/v1/proposals/{proposal_id}/export/pdf", headers=headers)
    docx = api.post(f"/api/v1/proposals/{proposal_id}/export/docx", headers=headers)
    assert pdf.status_code == 201, pdf.text
    assert docx.status_code == 201, docx.text
    downloaded = api.get(f"/api/v1/proposals/{proposal_id}/exports/{pdf.json()['id']}/download", headers=headers)
    assert downloaded.content.startswith(b"%PDF")
    summary = api.get("/api/v1/dashboard/summary", headers=headers, params={"company_id": company_id})
    assert summary.status_code == 200, summary.text
    assert summary.json()["approved"] == 1
    assert summary.json()["budgets"][0]["currency"] == "USD"
