"""Shared API test client."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_document_storage
from app.db.session import get_engine
from app.main import app
from app.storage.local import LocalDocumentStorage


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
def api(db_session: Session, document_storage: LocalDocumentStorage):
    """Test client bound to the rollback session and a temporary document store."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_document_storage] = lambda: document_storage
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_document_storage, None)
