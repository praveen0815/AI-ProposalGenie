"""Company membership, roles, and tenant isolation."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.company import Company
from app.models.enums import ProposalStatus
from app.models.proposal import Proposal
from app.repositories.proposals import list_for_company

PASSWORD = "Correct-horse-1"


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}@example.com"


def _auth(api: TestClient, prefix: str) -> dict[str, str]:
    email = _email(prefix)
    response = api.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": prefix.title()},
    )
    assert response.status_code == 201, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "email": email}


def _create_company(api: TestClient, headers: dict[str, str], name: str) -> dict:
    response = api.post("/api/v1/companies", headers=headers, json={"name": name, "industry": "Software"})
    assert response.status_code == 201, response.text
    return response.json()


def test_owner_can_create_and_list_only_their_companies(api: TestClient) -> None:
    owner = _auth(api, "owner")
    other = _auth(api, "other")
    created = _create_company(api, owner, "Northwind")
    _create_company(api, other, "Contoso")

    listing = api.get("/api/v1/companies", headers=owner)
    detail = api.get(f"/api/v1/companies/{created['id']}", headers=owner)
    hidden = api.get(f"/api/v1/companies/{created['id']}", headers=other)

    assert listing.status_code == 200
    assert [item["name"] for item in listing.json()] == ["Northwind"]
    assert listing.json()[0]["role"] == "OWNER"
    assert detail.status_code == 200
    assert detail.json()["industry"] == "Software"
    assert hidden.status_code == 404


def test_member_cannot_update_company_or_assign_roles(api: TestClient) -> None:
    owner = _auth(api, "owner")
    member = _auth(api, "member")
    admin = _auth(api, "admin")
    company = _create_company(api, owner, "Fabrikam")

    added_member = api.post(
        f"/api/v1/companies/{company['id']}/members",
        headers=owner,
        json={"email": member["email"], "role": "MEMBER"},
    )
    added_admin = api.post(
        f"/api/v1/companies/{company['id']}/members",
        headers=owner,
        json={"email": admin["email"], "role": "ADMIN"},
    )
    member_update = api.patch(
        f"/api/v1/companies/{company['id']}",
        headers=member,
        json={"description": "Members cannot edit this"},
    )
    admin_update = api.patch(
        f"/api/v1/companies/{company['id']}",
        headers=admin,
        json={"description": "Admin profile", "services": ["Discovery", "Delivery"]},
    )
    member_invite = api.post(
        f"/api/v1/companies/{company['id']}/members",
        headers=member,
        json={"email": _email("stranger"), "role": "MEMBER"},
    )
    admin_promotes = api.post(
        f"/api/v1/companies/{company['id']}/members",
        headers=admin,
        json={"email": _email("nobody"), "role": "ADMIN"},
    )

    assert added_member.status_code == 201
    assert added_admin.status_code == 201
    assert member_update.status_code == 403
    assert admin_update.status_code == 200
    assert admin_update.json()["description"] == "Admin profile"
    assert admin_update.json()["services"] == ["Discovery", "Delivery"]
    assert member_invite.status_code == 403
    assert admin_promotes.status_code == 403


def test_unknown_email_is_not_invited_and_duplicate_member_conflicts(api: TestClient) -> None:
    owner = _auth(api, "owner")
    member = _auth(api, "member")
    company = _create_company(api, owner, "Adventure Works")

    missing = api.post(
        f"/api/v1/companies/{company['id']}/members",
        headers=owner,
        json={"email": _email("missing"), "role": "MEMBER"},
    )
    first = api.post(
        f"/api/v1/companies/{company['id']}/members",
        headers=owner,
        json={"email": member["email"], "role": "MEMBER"},
    )
    second = api.post(
        f"/api/v1/companies/{company['id']}/members",
        headers=owner,
        json={"email": member["email"], "role": "ADMIN"},
    )

    assert missing.status_code == 404
    assert "create an account" in missing.json()["message"]
    assert first.status_code == 201
    assert second.status_code == 409


def test_only_an_owner_can_change_roles_and_the_last_owner_remains(api: TestClient) -> None:
    owner = _auth(api, "owner")
    admin = _auth(api, "admin")
    company = _create_company(api, owner, "Wide World")
    api.post(
        f"/api/v1/companies/{company['id']}/members",
        headers=owner,
        json={"email": admin["email"], "role": "ADMIN"},
    )
    members = api.get(f"/api/v1/companies/{company['id']}/members", headers=admin)
    owner_id = next(item["user_id"] for item in members.json() if item["role"] == "OWNER")
    admin_id = next(item["user_id"] for item in members.json() if item["role"] == "ADMIN")

    forbidden = api.patch(
        f"/api/v1/companies/{company['id']}/members/{admin_id}",
        headers=admin,
        json={"role": "MEMBER"},
    )
    demote_last_owner = api.patch(
        f"/api/v1/companies/{company['id']}/members/{owner_id}",
        headers=owner,
        json={"role": "ADMIN"},
    )
    promote = api.patch(
        f"/api/v1/companies/{company['id']}/members/{admin_id}",
        headers=owner,
        json={"role": "OWNER"},
    )
    demote_original = api.patch(
        f"/api/v1/companies/{company['id']}/members/{owner_id}",
        headers=owner,
        json={"role": "ADMIN"},
    )

    assert members.status_code == 200
    assert {item["role"] for item in members.json()} == {"OWNER", "ADMIN"}
    assert forbidden.status_code == 403
    assert demote_last_owner.status_code == 409
    assert promote.status_code == 200
    assert promote.json()["role"] == "OWNER"
    assert demote_original.status_code == 200
    assert demote_original.json()["role"] == "ADMIN"


def test_non_member_cannot_list_members(api: TestClient) -> None:
    owner = _auth(api, "owner")
    outsider = _auth(api, "outsider")
    company = _create_company(api, owner, "Alpine")

    response = api.get(f"/api/v1/companies/{company['id']}/members", headers=outsider)

    assert response.status_code == 404


def test_proposal_rows_stay_inside_their_company(api: TestClient, db_session: Session) -> None:
    first = _auth(api, "first")
    second = _auth(api, "second")
    first_company = _create_company(api, first, "First Co")
    second_company = _create_company(api, second, "Second Co")
    first_model = db_session.get(Company, first_company["id"])
    second_model = db_session.get(Company, second_company["id"])
    assert first_model is not None
    assert second_model is not None
    first_client = Client(company_id=first_model.id, name="Client A")
    db_session.add(first_client)
    db_session.flush()
    db_session.add_all(
        [
            Proposal(
                company_id=first_model.id,
                client_id=first_client.id,
                title="First proposal",
                status=ProposalStatus.DRAFT,
            ),
            Proposal(company_id=second_model.id, title="Second proposal", status=ProposalStatus.REVIEW),
        ]
    )
    db_session.commit()

    visible = list_for_company(db_session, first_model.id)

    assert [proposal.title for proposal in visible] == ["First proposal"]
    assert visible[0].client is not None
    assert visible[0].client.name == "Client A"
    assert visible[0].company_id != second_model.id
