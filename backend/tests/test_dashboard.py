"""Dashboard totals come from stored proposals."""

from uuid import uuid4

from fastapi.testclient import TestClient

PASSWORD = "Correct-horse-1"


def _auth(api: TestClient, prefix: str) -> dict[str, str]:
    response = api.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:10]}@example.com", "password": PASSWORD, "full_name": prefix.title()},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def _company(api: TestClient, headers: dict[str, str], name: str = "Northwind") -> str:
    response = api.post(
        "/api/v1/companies",
        headers=headers,
        json={"name": name, "industry": "Software", "description": "We deliver software projects."},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _proposal(api: TestClient, headers: dict[str, str], company_id: str, title: str) -> dict:
    response = api.post(
        "/api/v1/proposals",
        headers=headers,
        json={
            "company_id": company_id,
            "client_name": "Northwind Labs",
            "client_requirements": "Replace checkout.",
            "project_title": title,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _costs(api: TestClient, headers: dict[str, str], proposal_id: str, currency: str, price: str) -> None:
    response = api.put(
        f"/api/v1/proposals/{proposal_id}/costs",
        headers=headers,
        json={
            "currency": currency,
            "lines": [
                {
                    "name": "Consultant",
                    "category": "Labor",
                    "quantity": "1",
                    "unit": "person",
                    "unit_price": price,
                    "duration": "1",
                    "tax_percent": "0",
                    "discount_percent": "0",
                    "source": "CONFIRMED",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text


def _act(api: TestClient, headers: dict[str, str], proposal_id: str, action: str) -> None:
    response = api.post(f"/api/v1/proposals/{proposal_id}/approval", headers=headers, json={"action": action})
    assert response.status_code == 200, response.text


def test_summary_separates_currencies_and_hides_other_companies(api: TestClient) -> None:
    owner = _auth(api, "owner")
    outsider = _auth(api, "outsider")
    company_id = _company(api, owner)
    other_id = _company(api, outsider, "Other Co")
    draft = _proposal(api, owner, company_id, "Draft proposal")
    approved = _proposal(api, owner, company_id, "Approved proposal")
    sent = _proposal(api, owner, company_id, "Sent proposal")
    _costs(api, owner, draft["id"], "USD", "100")
    _costs(api, owner, approved["id"], "EUR", "40")
    _act(api, owner, approved["id"], "SUBMIT")
    _act(api, owner, approved["id"], "APPROVE")
    _act(api, owner, sent["id"], "SUBMIT")
    _act(api, owner, sent["id"], "APPROVE")
    _act(api, owner, sent["id"], "SEND")

    summary = api.get("/api/v1/dashboard/summary", headers=owner, params={"company_id": company_id})
    trends = api.get("/api/v1/dashboard/proposal-trends", headers=owner, params={"company_id": company_id})
    statuses = api.get("/api/v1/dashboard/status-distribution", headers=owner, params={"company_id": company_id})
    hidden = api.get("/api/v1/dashboard/summary", headers=outsider, params={"company_id": company_id})
    empty = api.get("/api/v1/dashboard/summary", headers=outsider, params={"company_id": other_id})

    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["total"] == 3
    assert body["draft"] == 1
    assert body["approved"] == 1
    assert body["sent"] == 1
    assert body["awaiting_review"] == 0
    assert body["conversion_rate"] == "0.5000"
    totals = {item["currency"]: item["grand_total"] for item in body["budgets"]}
    assert totals == {"EUR": "40.00", "USD": "100.00"}
    assert {item["title"] for item in body["recent"]} == {"Draft proposal", "Approved proposal", "Sent proposal"}
    assert sum(point["count"] for point in trends.json()["months"]) == 3
    assert len(trends.json()["months"]) == 12
    assert {item["status"]: item["count"] for item in statuses.json()["statuses"]}["DRAFT"] == 1
    assert hidden.status_code == 404
    assert empty.json()["total"] == 0
    assert empty.json()["conversion_rate"] is None
    assert empty.json()["budgets"] == []
    assert empty.json()["recent"] == []


def test_empty_trends_are_real_zero_counts(api: TestClient) -> None:
    owner = _auth(api, "empty")
    company_id = _company(api, owner, "Empty Co")
    trends = api.get("/api/v1/dashboard/proposal-trends", headers=owner, params={"company_id": company_id})
    statuses = api.get("/api/v1/dashboard/status-distribution", headers=owner, params={"company_id": company_id})

    assert trends.status_code == 200
    assert all(point["count"] == 0 for point in trends.json()["months"])
    assert all(item["count"] == 0 for item in statuses.json()["statuses"])
