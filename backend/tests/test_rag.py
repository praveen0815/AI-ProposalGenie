"""Indexing, isolation, retrieval, and grounded answers."""

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_embedding_service, get_vector_store
from app.main import app
from app.models.knowledge import KnowledgeDocument
from app.rag.vector_store import ChromaVectorStore, VectorStoreError
from tests.rag_fakes import FakeLanguageModel, HashEmbeddingService

PRICING = "Enterprise support pricing is 4000 dollars per year."
KITCHEN = "The office kitchen has a coffee machine and snacks."


def _register(api: TestClient, prefix: str) -> tuple[dict[str, str], str]:
    from uuid import uuid4

    response = api.post(
        "/api/v1/auth/register",
        json={"email": f"{prefix}-{uuid4().hex[:10]}@example.com", "password": "Correct-horse-1", "full_name": prefix.title()},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body["user"]["email"]


def _company(api: TestClient, headers: dict[str, str], name: str) -> str:
    response = api.post("/api/v1/companies", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload(api: TestClient, headers: dict[str, str], company_id: str, filename: str, content: bytes):
    return api.post(
        "/api/v1/knowledge/documents/upload",
        params={"company_id": company_id},
        headers=headers,
        files={"file": (filename, content, "text/plain")},
    )


class CountingEmbeddings(HashEmbeddingService):
    def __init__(self) -> None:
        self.document_calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return super().embed_documents(texts)


def test_chunks_are_indexed_once_and_persist(api: TestClient, tmp_path, language_model: FakeLanguageModel) -> None:
    embeddings = CountingEmbeddings()
    store = ChromaVectorStore(tmp_path / "persist", "company_knowledge")
    app.dependency_overrides[get_embedding_service] = lambda: embeddings
    app.dependency_overrides[get_vector_store] = lambda: store
    owner, _email = _register(api, "owner")
    company_id = _company(api, owner, "Indexed Co")
    created = _upload(api, owner, company_id, "pricing.txt", PRICING.encode())
    assert created.status_code == 201, created.text
    assert created.json()["index_status"] == "INDEXED"
    document_id = created.json()["id"]
    assert embeddings.document_calls == 1

    again = api.post(f"/api/v1/rag/index/document/{document_id}", headers=owner)
    assert again.status_code == 200, again.text
    assert again.json()["already_indexed"] is True
    assert embeddings.document_calls == 1

    rebuilt = api.post(f"/api/v1/rag/reindex/document/{document_id}", headers=owner)
    assert rebuilt.status_code == 200, rebuilt.text
    assert rebuilt.json()["already_indexed"] is False
    assert embeddings.document_calls == 2

    store.close()
    reopened = ChromaVectorStore(tmp_path / "persist", "company_knowledge")
    app.dependency_overrides[get_vector_store] = lambda: reopened
    found = api.post(
        "/api/v1/rag/search",
        headers=owner,
        json={"company_id": company_id, "query": "enterprise support pricing", "similarity_threshold": 0},
    )
    assert found.status_code == 200, found.text
    assert found.json()["results"][0]["document_id"] == document_id
    assert found.json()["results"][0]["source"] == "pricing.txt"
    reopened.close()
    assert language_model.calls == 0


def test_retrieval_is_company_scoped_and_relevant(api: TestClient, language_model: FakeLanguageModel) -> None:
    owner, _owner_email = _register(api, "owner")
    outsider, _outsider_email = _register(api, "outsider")
    member, member_email = _register(api, "member")
    company_id = _company(api, owner, "Alpha")
    other_company = _company(api, outsider, "Beta")
    added = api.post(
        f"/api/v1/companies/{company_id}/members",
        headers=owner,
        json={"email": member_email, "role": "MEMBER"},
    )
    assert added.status_code == 201, added.text

    pricing = _upload(api, owner, company_id, "pricing.txt", PRICING.encode())
    kitchen = _upload(api, owner, company_id, "kitchen.txt", KITCHEN.encode())
    leaked = _upload(api, outsider, other_company, "pricing.txt", PRICING.encode())
    assert pricing.status_code == 201
    assert kitchen.status_code == 201
    assert leaked.status_code == 201

    results = api.post(
        "/api/v1/rag/search",
        headers=owner,
        json={"company_id": company_id, "query": "enterprise support pricing", "top_k": 2, "similarity_threshold": 0},
    )
    assert results.status_code == 200, results.text
    identifiers = [item["document_id"] for item in results.json()["results"]]
    assert identifiers[0] == pricing.json()["id"]
    assert leaked.json()["id"] not in identifiers

    hidden = api.post("/api/v1/rag/search", headers=outsider, json={"company_id": company_id, "query": "pricing"})
    assert hidden.status_code == 404
    assert api.post("/api/v1/rag/search", json={"company_id": company_id, "query": "pricing"}).status_code == 401

    filtered = api.post(
        "/api/v1/rag/search",
        headers=owner,
        json={
            "company_id": company_id,
            "query": "pricing",
            "document_ids": [kitchen.json()["id"]],
            "similarity_threshold": 0,
        },
    )
    assert [item["document_id"] for item in filtered.json()["results"]] == [kitchen.json()["id"]]
    foreign = api.post(
        "/api/v1/rag/search",
        headers=owner,
        json={"company_id": company_id, "query": "pricing", "document_ids": [leaked.json()["id"]]},
    )
    assert foreign.status_code == 404

    forbidden = api.post(f"/api/v1/rag/reindex/document/{pricing.json()['id']}", headers=member)
    assert forbidden.status_code == 403


def test_missing_context_does_not_call_the_language_model(api: TestClient, language_model: FakeLanguageModel) -> None:
    owner, _email = _register(api, "owner")
    company_id = _company(api, owner, "Evidence")
    created = _upload(api, owner, company_id, "pricing.txt", PRICING.encode())
    assert created.status_code == 201

    answer = api.post(
        "/api/v1/rag/query",
        headers=owner,
        json={
            "company_id": company_id,
            "question": "quantum pretzel indemnity clause",
            "similarity_threshold": 0.99,
        },
    )
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert "don't have enough information" in body["answer"]
    assert body["context"] == []
    assert body["sources"] == []
    assert language_model.calls == 0

    grounded = api.post(
        "/api/v1/rag/query",
        headers=owner,
        json={"company_id": company_id, "question": "enterprise support pricing", "similarity_threshold": 0},
    )
    assert grounded.status_code == 200, grounded.text
    assert grounded.json()["sources"][0]["filename"] == "pricing.txt"
    assert grounded.json()["context"][0]["text"]
    assert language_model.calls == 1


def test_index_failures_and_deletion(
    api: TestClient,
    db_session: Session,
    vector_store: ChromaVectorStore,
    monkeypatch,
) -> None:
    owner, _email = _register(api, "owner")
    company_id = _company(api, owner, "Failures")

    class BrokenEmbeddings(HashEmbeddingService):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("model unavailable")

    class SearchFails:
        def replace_document(self, **kwargs) -> None:
            vector_store.replace_document(**kwargs)

        def delete_document(self, company_id: str, document_id: str) -> None:
            vector_store.delete_document(company_id, document_id)

        def query(self, **kwargs):
            raise VectorStoreError("store unavailable")

    app.dependency_overrides[get_embedding_service] = lambda: BrokenEmbeddings()
    failed = _upload(api, owner, company_id, "pricing.txt", PRICING.encode())
    assert failed.status_code == 201, failed.text
    assert failed.json()["index_status"] == "FAILED"
    document_id = failed.json()["id"]

    app.dependency_overrides[get_embedding_service] = lambda: HashEmbeddingService()
    indexed = api.post(f"/api/v1/rag/index/document/{document_id}", headers=owner)
    assert indexed.status_code == 200, indexed.text

    app.dependency_overrides[get_vector_store] = lambda: SearchFails()
    search_failed = api.post(
        "/api/v1/rag/search",
        headers=owner,
        json={"company_id": company_id, "query": "pricing", "similarity_threshold": 0},
    )
    assert search_failed.status_code == 503
    app.dependency_overrides[get_vector_store] = lambda: vector_store

    original_commit = db_session.commit

    def fail_commit() -> None:
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    database_failed = api.post(f"/api/v1/rag/reindex/document/{document_id}", headers=owner)
    assert database_failed.status_code == 503
    monkeypatch.setattr(db_session, "commit", original_commit)

    removed = api.delete(f"/api/v1/rag/index/document/{document_id}", headers=owner)
    assert removed.status_code == 200, removed.text
    assert removed.json()["index_status"] == "NOT_INDEXED"
    assert db_session.get(KnowledgeDocument, UUID(document_id)) is not None
    empty = api.post(
        "/api/v1/rag/search",
        headers=owner,
        json={"company_id": company_id, "query": "enterprise support pricing", "similarity_threshold": 0},
    )
    assert empty.status_code == 200
    assert empty.json()["results"] == []
