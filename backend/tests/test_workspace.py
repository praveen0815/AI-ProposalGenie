"""Proposal editing, versions, costs, and approval."""

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_proposal_model
from app.integrations.llm.types import Completion, TokenUsage
from app.main import app

PASSWORD = "Correct-horse-1"


class ScriptedModel:
    model_name = "fake-gemini"

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def generate_json(self, *, purpose: str, prompt: str, schema: dict) -> Completion:
        return Completion(text=json.dumps(self.payload), model=self.model_name, usage=TokenUsage(1, 1, 2))


def _auth(api: TestClient, prefix: str) -> dict[str, str]:
    response = api.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:10]}@example.com", "password": PASSWORD, "full_name": prefix.title()},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}", "email": body["user"]["email"]}


def _company(api: TestClient, headers: dict[str, str]) -> str:
    response = api.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": "Northwind", "industry": "Software", "description": "We deliver software projects."},
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
            "client_requirements": "Replace checkout.",
            "project_title": "Checkout modernization",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _save(api: TestClient, headers: dict[str, str], proposal_id: str, revision: int, title: str, sections: list[dict]) -> dict:
    response = api.put(
        f"/api/v1/proposals/{proposal_id}/draft",
        headers=headers,
        json={"title": title, "expected_revision": revision, "sections": sections},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_editing_detects_a_stale_autosave_and_keeps_versions(api: TestClient) -> None:
    owner = _auth(api, "owner")
    proposal = _proposal(api, owner, _company(api, owner))
    first = _save(api, owner, proposal["id"], 0, "Checkout modernization", [{"title": "Scope", "body": "First draft"}])
    conflict = api.put(
        f"/api/v1/proposals/{proposal['id']}/draft",
        headers=owner,
        json={"title": "Stale", "expected_revision": 0, "sections": [{"title": "Scope", "body": "Old"}]},
    )
    second = _save(
        api,
        owner,
        proposal["id"],
        first["content_revision"],
        "Checkout modernization",
        [{"id": first["sections"][0]["id"], "title": "Scope", "body": "Second draft"}],
    )
    created = api.post(
        f"/api/v1/proposals/{proposal['id']}/versions",
        headers=owner,
        json={"change_description": "Saved the second draft"},
    )
    listed = api.get(f"/api/v1/proposals/{proposal['id']}/versions", headers=owner)

    assert conflict.status_code == 409
    assert second["sections"][0]["body"] == "Second draft"
    assert second["content_revision"] == 2
    assert created.status_code == 201
    assert created.json()["change_description"] == "Saved the second draft"
    assert listed.json()[0]["version_number"] == 1


def test_restore_creates_a_new_version_and_keeps_the_old_one(api: TestClient) -> None:
    owner = _auth(api, "owner")
    proposal = _proposal(api, owner, _company(api, owner))
    first = _save(api, owner, proposal["id"], 0, "Checkout modernization", [{"title": "Scope", "body": "Original scope"}])
    first_version = api.post(
        f"/api/v1/proposals/{proposal['id']}/versions",
        headers=owner,
        json={"change_description": "Original"},
    )
    _save(
        api,
        owner,
        proposal["id"],
        first["content_revision"],
        "Checkout modernization",
        [{"id": first["sections"][0]["id"], "title": "Scope", "body": "Edited scope"}],
    )
    second_version = api.post(
        f"/api/v1/proposals/{proposal['id']}/versions",
        headers=owner,
        json={"change_description": "Edited"},
    )
    restored = api.post(
        f"/api/v1/proposals/{proposal['id']}/versions/{first_version.json()['id']}/restore",
        headers=owner,
    )
    history = api.get(f"/api/v1/proposals/{proposal['id']}/versions", headers=owner)
    original = api.get(f"/api/v1/proposals/{proposal['id']}/versions/{first_version.json()['id']}", headers=owner)
    comparison = api.get(
        f"/api/v1/proposals/{proposal['id']}/versions/compare",
        headers=owner,
        params={"left_id": first_version.json()["id"], "right_id": second_version.json()["id"]},
    )

    assert restored.status_code == 200, restored.text
    assert restored.json()["sections"][0]["body"] == "Original scope"
    assert original.status_code == 200
    assert original.json()["snapshot"]["sections"][0]["body"] == "Original scope"
    assert any(item["change_description"].startswith("Restored version") for item in history.json())
    assert comparison.json()["changes"][0]["change"] == "changed"


def test_regeneration_does_not_replace_a_user_edit_until_confirmed(api: TestClient) -> None:
    owner = _auth(api, "owner")
    proposal = _proposal(api, owner, _company(api, owner))
    saved = _save(api, owner, proposal["id"], 0, "Checkout modernization", [{"title": "Scope", "body": "User wording"}])
    app.dependency_overrides[get_proposal_model] = lambda: ScriptedModel({"body": "AI draft. Revised scope."})
    section_id = saved["sections"][0]["id"]

    preview = api.post(
        f"/api/v1/proposals/{proposal['id']}/sections/{section_id}/regenerate",
        headers=owner,
        json={"confirm_overwrite": False},
    )
    applied = api.post(
        f"/api/v1/proposals/{proposal['id']}/sections/{section_id}/regenerate",
        headers=owner,
        json={"confirm_overwrite": True},
    )

    assert preview.status_code == 200
    assert preview.json()["applied"] is False
    assert preview.json()["section"]["body"] == "User wording"
    assert applied.json()["applied"] is True
    assert applied.json()["previous_body"] == "User wording"
    assert applied.json()["section"]["body"].startswith("AI draft.")
    assert applied.json()["section"]["ai_body"] == applied.json()["section"]["body"]


def test_cost_sheet_uses_decimal_totals_and_confirmation(api: TestClient) -> None:
    owner = _auth(api, "owner")
    proposal = _proposal(api, owner, _company(api, owner))
    invalid = api.put(
        f"/api/v1/proposals/{proposal['id']}/costs",
        headers=owner,
        json={"currency": "US", "lines": []},
    )
    saved = api.put(
        f"/api/v1/proposals/{proposal['id']}/costs",
        headers=owner,
        json={
            "currency": "usd",
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
    app.dependency_overrides[get_proposal_model] = lambda: ScriptedModel(
        {
            "lines": [
                {
                    "name": "Suggested license",
                    "category": "Software",
                    "quantity": "1",
                    "unit": "license",
                    "unit_price": "50",
                    "duration": "1",
                    "tax_percent": "0",
                    "discount_percent": "0",
                }
            ]
        }
    )
    suggested = api.post(f"/api/v1/proposals/{proposal['id']}/costs/suggest", headers=owner, params={"currency": "USD"})
    estimate = next(line for line in suggested.json()["lines"] if line["source"] == "ESTIMATED")
    confirmed = api.post(f"/api/v1/proposals/{proposal['id']}/costs/items/{estimate['id']}/confirm", headers=owner)

    assert invalid.status_code == 422
    assert saved.status_code == 200, saved.text
    assert saved.json()["currency"] == "USD"
    assert saved.json()["grand_total"] == "627.00"
    assert saved.json()["tax"] == "57.00"
    assert saved.json()["discount"] == "30.00"
    assert saved.json()["lines"][0]["source"] == "CONFIRMED"
    assert suggested.json()["estimated_count"] == 1
    assert estimate["unit_price"] == "50.00"
    assert confirmed.json()["confirmed_count"] == 2
    assert confirmed.json()["estimated_count"] == 0
    assert confirmed.json()["grand_total"] == "677.00"


def test_approval_permissions_transitions_and_audit(api: TestClient) -> None:
    owner = _auth(api, "owner")
    member = _auth(api, "member")
    company_id = _company(api, owner)
    added = api.post(
        f"/api/v1/companies/{company_id}/members",
        headers=owner,
        json={"email": member["email"], "role": "MEMBER"},
    )
    assert added.status_code == 201, added.text
    proposal = _proposal(api, owner, company_id)

    member_submit = api.post(
        f"/api/v1/proposals/{proposal['id']}/approval",
        headers=member,
        json={"action": "SUBMIT"},
    )
    submitted = api.post(
        f"/api/v1/proposals/{proposal['id']}/approval",
        headers=owner,
        json={"action": "SUBMIT"},
    )
    member_approve = api.post(
        f"/api/v1/proposals/{proposal['id']}/approval",
        headers=member,
        json={"action": "APPROVE"},
    )
    missing_comment = api.post(
        f"/api/v1/proposals/{proposal['id']}/approval",
        headers=owner,
        json={"action": "REQUEST_CHANGES"},
    )
    sent_too_early = api.post(
        f"/api/v1/proposals/{proposal['id']}/approval",
        headers=owner,
        json={"action": "SEND"},
    )
    approved = api.post(
        f"/api/v1/proposals/{proposal['id']}/approval",
        headers=owner,
        json={"action": "APPROVE"},
    )
    history = api.get(f"/api/v1/proposals/{proposal['id']}/approval", headers=owner)

    assert member_submit.status_code == 403
    assert submitted.status_code == 200
    assert member_approve.status_code == 403
    assert submitted.json()["status"] == "REVIEW"
    assert missing_comment.status_code == 422
    assert sent_too_early.status_code == 409
    assert approved.json()["status"] == "APPROVED"
    assert [event["action"] for event in history.json()] == ["SUBMIT", "APPROVE"]
    assert history.json()[0]["from_status"] == "DRAFT"
    assert history.json()[1]["to_status"] == "APPROVED"
