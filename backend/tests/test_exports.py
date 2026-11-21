"""PDF and DOCX export."""

import io
from uuid import uuid4

import fitz
from docx import Document
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from app.exports.pdf import ExportError
from app.models.company import Company
from app.storage.local import LocalDocumentStorage

PASSWORD = "Correct-horse-1"


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


def _ready(api: TestClient, headers: dict[str, str]) -> dict:
    proposal = _proposal(api, headers, _company(api, headers))
    long_scope = "\n".join(f"Scope line {index} stays in the exported document." for index in range(1, 90))
    long_scope += "\nUNIQUE-END-OF-SCOPE"
    saved = api.put(
        f"/api/v1/proposals/{proposal['id']}/draft",
        headers=headers,
        json={
            "title": "Checkout modernization",
            "expected_revision": proposal["content_revision"],
            "sections": [
                {"title": "Executive Summary", "body": "The executive summary for checkout."},
                {"title": "Deliverables", "body": "Working checkout."},
                {"title": "Project Timeline", "body": "Four weeks."},
                {"title": "Terms and Conditions", "body": "Payment in 30 days."},
                {"title": "Scope of Work", "body": long_scope},
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    costs = api.put(
        f"/api/v1/proposals/{proposal['id']}/costs",
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
    review = api.post(
        f"/api/v1/proposals/{proposal['id']}/approval",
        headers=headers,
        json={"action": "SUBMIT"},
    )
    assert review.status_code == 200, review.text
    return review.json()


def test_pdf_and_docx_contain_the_proposal_and_can_be_downloaded(api: TestClient, db_session: Session, document_storage: LocalDocumentStorage) -> None:
    owner = _auth(api, "owner")
    proposal = _ready(api, owner)
    company = db_session.get(Company, proposal["company_id"])
    assert company is not None
    logo = io.BytesIO()
    Image.new("RGB", (16, 16), (14, 58, 77)).save(logo, format="PNG")
    logo_path = document_storage.root / "brand" / "logo.png"
    logo_path.parent.mkdir(parents=True, exist_ok=True)
    logo_path.write_bytes(logo.getvalue())
    company.logo_storage_key = "brand/logo.png"
    db_session.commit()

    pdf = api.post(f"/api/v1/proposals/{proposal['id']}/export/pdf", headers=owner)
    docx = api.post(f"/api/v1/proposals/{proposal['id']}/export/docx", headers=owner)
    listed = api.get(f"/api/v1/proposals/{proposal['id']}/exports", headers=owner)

    assert pdf.status_code == 201, pdf.text
    assert docx.status_code == 201, docx.text
    assert "storage_key" not in pdf.text
    assert "brand/logo.png" not in pdf.text
    assert pdf.json()["filename"].endswith(".pdf")
    assert docx.json()["content_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert listed.json()[0]["stale"] is False

    pdf_file = api.get(f"/api/v1/proposals/{proposal['id']}/exports/{pdf.json()['id']}/download", headers=owner)
    docx_file = api.get(f"/api/v1/proposals/{proposal['id']}/exports/{docx.json()['id']}/download", headers=owner)
    assert pdf_file.status_code == 200
    assert pdf_file.headers["content-type"].startswith("application/pdf")
    assert "attachment;" in pdf_file.headers["content-disposition"]
    assert "\\" not in pdf_file.headers["content-disposition"]
    assert pdf_file.content.startswith(b"%PDF")
    opened = fitz.open(stream=pdf_file.content, filetype="pdf")
    text = " ".join("\n".join(page.get_text() for page in opened).split())
    assert opened.page_count > 1
    assert opened[0].get_images()
    assert "Checkout modernization" in text
    assert "Northwind Labs" in text
    assert "The executive summary for checkout." in text
    assert "Working checkout." in text
    assert "Four weeks." in text
    assert "Payment in 30 days." in text
    assert "UNIQUE-END-OF-SCOPE" in text
    assert "627.00" in text
    assert "Page 1" in text
    opened.close()

    word = Document(io.BytesIO(docx_file.content))
    word_text = "\n".join(paragraph.text for paragraph in word.paragraphs)
    table_text = "\n".join(cell.text for table in word.tables for row in table.rows for cell in row.cells)
    assert "Checkout modernization" in word_text
    assert "The executive summary for checkout." in word_text
    assert "UNIQUE-END-OF-SCOPE" in word_text
    assert "Consultant" in table_text
    assert "627.00" in word_text
    assert "PAGE" in word.sections[0].footer._element.xml


def test_export_is_rejected_for_drafts_missing_proposals_and_failures(api: TestClient, monkeypatch) -> None:
    owner = _auth(api, "owner")
    outsider = _auth(api, "outsider")
    proposal = _proposal(api, owner, _company(api, owner))
    draft = api.post(f"/api/v1/proposals/{proposal['id']}/export/pdf", headers=owner)
    missing = api.post(f"/api/v1/proposals/{uuid4()}/export/pdf", headers=owner)
    hidden = api.post(f"/api/v1/proposals/{proposal['id']}/export/docx", headers=outsider)
    anonymous = api.get(f"/api/v1/proposals/{proposal['id']}/exports")

    ready = _ready(api, owner)

    def fail(document):
        raise ExportError(r"C:\secret\proposal.pdf")

    monkeypatch.setattr("app.services.exports.render_pdf", fail)
    failed = api.post(f"/api/v1/proposals/{ready['id']}/export/pdf", headers=owner)
    remaining = api.get(f"/api/v1/proposals/{ready['id']}/exports", headers=owner)

    assert draft.status_code == 409
    assert missing.status_code == 404
    assert hidden.status_code == 404
    assert anonymous.status_code == 401
    assert failed.status_code == 500
    assert "secret" not in failed.text
    assert remaining.json() == []


def test_a_new_export_keeps_the_previous_file_and_marks_it_stale(api: TestClient) -> None:
    owner = _auth(api, "owner")
    proposal = _ready(api, owner)
    first = api.post(f"/api/v1/proposals/{proposal['id']}/export/pdf", headers=owner)
    assert first.status_code == 201, first.text
    edited = api.put(
        f"/api/v1/proposals/{proposal['id']}/draft",
        headers=owner,
        json={
            "title": "Checkout modernization revised",
            "expected_revision": first.json()["current_revision"],
            "sections": [{"title": "Executive Summary", "body": "Revised summary."}],
        },
    )
    assert edited.status_code == 200, edited.text
    second = api.post(f"/api/v1/proposals/{proposal['id']}/export/pdf", headers=owner)
    history = api.get(f"/api/v1/proposals/{proposal['id']}/exports", headers=owner)
    old = api.get(f"/api/v1/proposals/{proposal['id']}/exports/{first.json()['id']}/download", headers=owner)

    assert second.status_code == 201, second.text
    assert len(history.json()) == 2
    stale = next(item for item in history.json() if item["id"] == first.json()["id"])
    assert stale["stale"] is True
    assert old.status_code == 200
    assert "The executive summary for checkout." in " ".join(_pdf_text(old.content).split())


def _pdf_text(payload: bytes) -> str:
    opened = fitz.open(stream=payload, filetype="pdf")
    text = "\n".join(page.get_text() for page in opened)
    opened.close()
    return text
