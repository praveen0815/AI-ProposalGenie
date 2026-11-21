"""Shared API test client."""

import os

os.environ["RATE_LIMIT_ENABLED"] = "false"

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_document_storage,
    get_embedding_service,
    get_language_model,
    get_proposal_model,
    get_vector_store,
)
from app.db.session import get_engine
from app.main import app
from app.rag.vector_store import ChromaVectorStore
from app.storage.local import LocalDocumentStorage
from tests.proposal_fakes import FakeProposalModel
from tests.rag_fakes import FakeLanguageModel, HashEmbeddingService


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    """Session whose work is rolled back when the test ends."""

    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def document_storage(tmp_path: Path) -> LocalDocumentStorage:
    """Private temp directory so tests do not write into the development store."""

    return LocalDocumentStorage(tmp_path / "documents")


@pytest.fixture
def embedding_service() -> HashEmbeddingService:
    return HashEmbeddingService()


@pytest.fixture
def vector_store(tmp_path: Path) -> ChromaVectorStore:
    return ChromaVectorStore(tmp_path / "chroma", "company_knowledge")


@pytest.fixture
def language_model() -> FakeLanguageModel:
    return FakeLanguageModel()


@pytest.fixture
def proposal_model() -> FakeProposalModel:
    return FakeProposalModel()


@pytest.fixture
def api(
    db_session: Session,
    document_storage: LocalDocumentStorage,
    embedding_service: HashEmbeddingService,
    vector_store: ChromaVectorStore,
    language_model: FakeLanguageModel,
    proposal_model: FakeProposalModel,
):
    """Test client bound to the rollback session, temporary files, and fake retrieval models."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_document_storage] = lambda: document_storage
    app.dependency_overrides[get_embedding_service] = lambda: embedding_service
    app.dependency_overrides[get_vector_store] = lambda: vector_store
    app.dependency_overrides[get_language_model] = lambda: language_model
    app.dependency_overrides[get_proposal_model] = lambda: proposal_model
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        vector_store.close()
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_document_storage, None)
        app.dependency_overrides.pop(get_embedding_service, None)
        app.dependency_overrides.pop(get_vector_store, None)
        app.dependency_overrides.pop(get_language_model, None)
        app.dependency_overrides.pop(get_proposal_model, None)
