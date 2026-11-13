"""Knowledge document API, isolation, and processing."""

import zipfile
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_document_storage
from app.core.config import get_settings
from app.main import app
from app.models.enums import DocumentProcessingStatus
from app.models.knowledge import DocumentProcessingJob, KnowledgeDocument
from app.storage.base import StorageError
from app.storage.local import LocalDocumentStorage

PASSWORD = "Correct-horse-1"
MARKER = "Acme delivery timeline"


def _register(api: TestClient, prefix: str) -> tuple[dict[str, str], str, str]:
    response = api.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:10]}@example.com", "password": PASSWORD, "full_name": prefix.title()},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    return headers, body["user"]["id"], body["user"]["email"]


def _company(api: TestClient, headers: dict[str, str]) -> str:
    response = api.post("/api/v1/companies", headers=headers, json={"name": "Knowledge Co"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload(
    api: TestClient,
    headers: dict[str, str],
    company_id: str,
    filename: str,
    content: bytes,
    content_type: str | None = None,
):
    file_part = (filename, content, content_type) if content_type else (filename, content)
    return api.post(
        "/api/v1/knowledge/documents/upload",
        params={"company_id": company_id},
        headers=headers,
        files={"file": file_part},
    )


def _pdf(text: str) -> bytes:
    import pymupdf

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    payload = document.tobytes()
    document.close()
    return payload


def _docx(text: str) -> bytes:
    from docx import Document

    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_upload_extracts_supported_files_without_returning_the_text(api: TestClient, db_session: Session) -> None:
    owner, _user_id, _email = _register(api, "owner")
    company_id = _company(api, owner)
    uploads = [
        ("brief.txt", f"{MARKER}\n".encode(), "text/plain"),
        ("brief.md", b"# Heading\n\nMarkdown body", "text/markdown"),
        ("brief.pdf", _pdf(MARKER), "application/pdf"),
        ("brief.docx", _docx(MARKER), None),
    ]

    for filename, content, content_type in uploads:
        response = _upload(api, owner, company_id, filename, content, content_type)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["processing_status"] == "COMPLETED"
        assert body["character_count"] > 0
        assert "extracted_text" not in body
        assert "storage_key" not in body
        assert MARKER not in response.text
        stored = db_session.get(KnowledgeDocument, UUID(body["id"]))
        assert stored is not None
        assert stored.extracted_text is not None
        assert ".." not in stored.storage_key
        if filename.endswith(".md"):
            assert "Markdown body" in stored.extracted_text
        else:
            assert MARKER in stored.extracted_text

    listing = api.get("/api/v1/knowledge/documents", params={"company_id": company_id}, headers=owner)
    assert listing.status_code == 200
    assert len(listing.json()) == 4
    assert MARKER not in listing.text


def test_validation_errors_do_not_store_a_document(api: TestClient, db_session: Session, monkeypatch) -> None:
    owner, _user_id, _email = _register(api, "owner")
    company_id = _company(api, owner)
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 32)

    empty = _upload(api, owner, company_id, "empty.txt", b"", "text/plain")
    oversized = _upload(api, owner, company_id, "large.txt", b"x" * 33, "text/plain")
    unsupported = _upload(api, owner, company_id, "picture.png", b"\x89PNG", "image/png")
    mismatch = _upload(api, owner, company_id, "notes.pdf", b"plain words", "application/pdf")
    declared = _upload(api, owner, company_id, "notes.txt", b"plain words", "application/pdf")
    traversal = _upload(api, owner, company_id, "../../secret.txt", b"kept inside", "text/plain")

    assert empty.status_code == 422
    assert oversized.status_code == 413
    assert unsupported.status_code == 415
    assert mismatch.status_code == 422
    assert declared.status_code == 415
    assert traversal.status_code == 201
    assert traversal.json()["original_filename"] == "secret.txt"
    stored_count = db_session.scalar(select(func.count()).select_from(KnowledgeDocument))
    assert stored_count == 1


def test_corrupt_documents_are_stored_as_failed(api: TestClient) -> None:
    owner, _user_id, _email = _register(api, "owner")
    company_id = _company(api, owner)
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types></Types>")
        archive.writestr("word/document.xml", "not xml")

    pdf = _upload(api, owner, company_id, "broken.pdf", b"%PDF-1.7\nnot a real pdf", "application/pdf")
    docx = _upload(api, owner, company_id, "broken.docx", buffer.getvalue())
    blank = _upload(api, owner, company_id, "blank.txt", b"   \n", "text/plain")

    assert pdf.status_code == 201
    assert pdf.json()["processing_status"] == "FAILED"
    assert docx.status_code == 201
    assert docx.json()["processing_status"] == "FAILED"
    assert blank.status_code == 201
    assert blank.json()["processing_error"] == "The file has no extractable text"


def test_document_limit(api: TestClient, monkeypatch) -> None:
    owner, _user_id, _email = _register(api, "owner")
    company_id = _company(api, owner)
    monkeypatch.setattr(get_settings(), "max_documents_per_company", 1)
    first = _upload(api, owner, company_id, "one.txt", b"first document", "text/plain")
    second = _upload(api, owner, company_id, "two.txt", b"second document", "text/plain")

    assert first.status_code == 201
    assert second.status_code == 409


def test_permissions_isolation_delete_and_reprocess(
    api: TestClient,
    db_session: Session,
    document_storage: LocalDocumentStorage,
) -> None:
    owner, _owner_id, _owner_email = _register(api, "owner")
    member, _member_id, member_email = _register(api, "member")
    outsider, _outsider_id, _outsider_email = _register(api, "outsider")
    company_id = _company(api, owner)
    other_company = _company(api, outsider)
    added = api.post(
        f"/api/v1/companies/{company_id}/members",
        headers=owner,
        json={"email": member_email, "role": "MEMBER"},
    )
    assert added.status_code == 201, added.text

    created = _upload(api, owner, company_id, "private.txt", MARKER.encode(), "text/plain")
    assert created.status_code == 201, created.text
    document_id = created.json()["id"]
    stored = db_session.get(KnowledgeDocument, UUID(document_id))
    assert stored is not None
    document_storage.read(stored.storage_key)

    assert api.get("/api/v1/knowledge/documents", params={"company_id": company_id}).status_code == 401
    assert api.get(f"/api/v1/knowledge/documents/{document_id}", headers=outsider).status_code == 404
    assert api.get(f"/api/v1/knowledge/documents/{document_id}/status", headers=outsider).status_code == 404
    assert api.delete(f"/api/v1/knowledge/documents/{document_id}", headers=outsider).status_code == 404
    hidden = api.get("/api/v1/knowledge/documents", params={"company_id": company_id}, headers=outsider)
    assert hidden.status_code == 404
    other_list = api.get("/api/v1/knowledge/documents", params={"company_id": other_company}, headers=outsider)
    assert other_list.json() == []

    assert api.delete(f"/api/v1/knowledge/documents/{document_id}", headers=member).status_code == 403
    assert api.post(f"/api/v1/knowledge/documents/{document_id}/reprocess", headers=member).status_code == 403

    detail = api.get(f"/api/v1/knowledge/documents/{document_id}", headers=owner)
    status = api.get(f"/api/v1/knowledge/documents/{document_id}/status", headers=owner)
    assert detail.status_code == 200
    assert status.json()["processing_status"] == "COMPLETED"
    assert MARKER not in detail.text

    retried = api.post(f"/api/v1/knowledge/documents/{document_id}/reprocess", headers=owner)
    assert retried.status_code == 200
    assert retried.json()["processing_status"] == "COMPLETED"
    jobs = db_session.scalars(
        select(DocumentProcessingJob).where(DocumentProcessingJob.document_id == UUID(document_id))
    ).all()
    assert len(jobs) == 2

    stored.processing_status = DocumentProcessingStatus.PROCESSING
    db_session.commit()
    assert api.post(f"/api/v1/knowledge/documents/{document_id}/reprocess", headers=owner).status_code == 409
    stored.processing_status = DocumentProcessingStatus.COMPLETED
    db_session.commit()

    assert api.delete(f"/api/v1/knowledge/documents/{document_id}", headers=owner).status_code == 204
    assert api.get(f"/api/v1/knowledge/documents/{document_id}", headers=owner).status_code == 404
    with pytest.raises(StorageError):
        document_storage.read(stored.storage_key)


def test_storage_failures_do_not_leave_a_saved_row(api: TestClient, tmp_path, db_session: Session) -> None:
    owner, _user_id, _email = _register(api, "owner")
    company_id = _company(api, owner)

    class SaveFails(LocalDocumentStorage):
        def save(self, key: str, data: bytes) -> None:
            raise StorageError("The document could not be stored")

    class DeleteFails(LocalDocumentStorage):
        def delete(self, key: str) -> None:
            raise StorageError("The stored file could not be deleted")

    app.dependency_overrides[get_document_storage] = lambda: SaveFails(tmp_path / "save-fails")
    failed = _upload(api, owner, company_id, "notes.txt", b"will not be stored", "text/plain")
    assert failed.status_code == 503
    assert db_session.scalars(select(KnowledgeDocument)).all() == []

    app.dependency_overrides[get_document_storage] = lambda: DeleteFails(tmp_path / "delete-fails")
    created = _upload(api, owner, company_id, "notes.txt", b"stored then locked", "text/plain")
    assert created.status_code == 201, created.text
    deleted = api.delete(f"/api/v1/knowledge/documents/{created.json()['id']}", headers=owner)
    assert deleted.status_code == 503
    assert db_session.get(KnowledgeDocument, UUID(created.json()["id"])) is not None
