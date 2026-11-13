"""Model metadata is the Alembic target."""

from app import models
from app.db.base import Base


def test_model_package_exposes_the_declarative_base() -> None:
    assert models.Base is Base


def test_domain_models_are_registered() -> None:
    assert set(models.Base.metadata.tables) == {
        "users",
        "companies",
        "company_memberships",
        "clients",
        "proposals",
        "proposal_sections",
        "proposal_versions",
        "knowledge_documents",
        "document_processing_jobs",
    }
