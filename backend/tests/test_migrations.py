"""The upgraded schema matches the Phase 2 models."""

from sqlalchemy import inspect

from app.db.session import get_engine

EXPECTED_TABLES = {
    "users",
    "companies",
    "company_memberships",
    "clients",
    "proposals",
    "proposal_sections",
    "proposal_versions",
    "knowledge_documents",
    "document_processing_jobs",
    "agent_runs",
    "agent_events",
}


def test_phase_two_tables_exist() -> None:
    tables = set(inspect(get_engine()).get_table_names())

    assert EXPECTED_TABLES <= tables


def test_user_email_is_unique_and_password_hash_is_required() -> None:
    inspector = inspect(get_engine())
    columns = {column["name"]: column for column in inspector.get_columns("users")}
    unique_indexes = [index for index in inspector.get_indexes("users") if index.get("unique")]
    unique_constraints = inspector.get_unique_constraints("users")

    assert columns["email"]["nullable"] is False
    assert columns["password_hash"]["nullable"] is False
    assert any("email" in index["column_names"] for index in unique_indexes) or any(
        "email" in constraint["column_names"] for constraint in unique_constraints
    )


def _ondelete(table: str, column: str) -> str | None:
    for foreign_key in inspect(get_engine()).get_foreign_keys(table):
        if column in foreign_key["constrained_columns"]:
            return foreign_key.get("options", {}).get("ondelete")
    return None


def test_foreign_keys_use_the_expected_delete_behavior() -> None:
    assert _ondelete("company_memberships", "company_id") == "CASCADE"
    assert _ondelete("company_memberships", "user_id") == "CASCADE"
    assert _ondelete("clients", "company_id") == "CASCADE"
    assert _ondelete("proposals", "company_id") == "CASCADE"
    assert _ondelete("proposals", "client_id") == "SET NULL"
    assert _ondelete("proposals", "owner_id") == "SET NULL"
    assert _ondelete("proposal_sections", "proposal_id") == "CASCADE"
    assert _ondelete("proposal_versions", "proposal_id") == "CASCADE"
    assert _ondelete("proposal_versions", "created_by_id") == "SET NULL"
    assert _ondelete("knowledge_documents", "company_id") == "CASCADE"
    assert _ondelete("knowledge_documents", "uploaded_by_id") == "SET NULL"
    assert _ondelete("document_processing_jobs", "document_id") == "CASCADE"


def test_proposals_store_generation_metadata() -> None:
    columns = {column["name"]: column for column in inspect(get_engine()).get_columns("proposals")}
    section_columns = {column["name"]: column for column in inspect(get_engine()).get_columns("proposal_sections")}

    assert columns["generation_input"]["nullable"] is True
    assert columns["generation_metadata"]["nullable"] is True
    assert columns["model_name"]["nullable"] is True
    assert columns["generated_at"]["nullable"] is True
    assert section_columns["needs_review"]["nullable"] is False
    assert section_columns["source_references"]["nullable"] is False


def test_knowledge_documents_track_index_status() -> None:
    columns = {column["name"]: column for column in inspect(get_engine()).get_columns("knowledge_documents")}

    assert columns["index_status"]["nullable"] is False
    assert columns["content_hash"]["nullable"] is True
    assert columns["chunk_count"]["nullable"] is True
