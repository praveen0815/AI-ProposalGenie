"""Index company documents and answer questions from retrieved chunks."""

import hashlib
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import DocumentProcessingStatus, IndexStatus, MembershipRole
from app.models.knowledge import KnowledgeDocument
from app.models.membership import CompanyMembership
from app.models.user import User
from app.rag.document_loader import load_pages
from app.rag.embedding_service import EmbeddingService
from app.rag.llm import LanguageModel, LanguageModelError
from app.rag.retriever import RetrievedChunk, retrieve
from app.rag.text_splitter import split_pages
from app.rag.vector_store import VectorStore, VectorStoreError
from app.repositories import knowledge as knowledge_repository
from app.repositories import memberships as membership_repository
from app.schemas.rag import IndexResponse, QueryResponse, RetrievedChunkResponse, SearchResponse, SourceDocument

logger = logging.getLogger(__name__)

INSUFFICIENT_ANSWER = "I don't have enough information in the company documents to answer that."
_MANAGERS = {MembershipRole.OWNER, MembershipRole.ADMIN}


def index_document(
    db: Session,
    embeddings: EmbeddingService,
    store: VectorStore,
    actor: User,
    document_id: UUID,
    *,
    force: bool,
) -> IndexResponse:
    document, membership = _visible_document(db, actor, document_id)
    _require_manage(membership, document, actor)
    if document.processing_status != DocumentProcessingStatus.COMPLETED or not (document.extracted_text or "").strip():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document text is not ready to index")

    settings = get_settings()
    pages = load_pages(document)
    chunks = split_pages(document.original_filename, pages, settings.rag_chunk_size, settings.rag_chunk_overlap)
    if not chunks:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="The document has no text to index")

    digest = hashlib.sha256("\n".join(chunk.text for chunk in chunks).encode()).hexdigest()
    if not force and document.index_status == IndexStatus.INDEXED and document.content_hash == digest:
        return _index_response(document, already_indexed=True)

    try:
        document.index_status = IndexStatus.INDEXING
        document.index_error = None
        document.updated_at = datetime.now(UTC)
        db.commit()
        vectors = embeddings.embed_documents([chunk.text for chunk in chunks])
        company_id = str(document.company_id)
        document_key = str(document.id)
        store.replace_document(
            company_id=company_id,
            document_id=document_key,
            ids=[f"{document_key}:{chunk.index}" for chunk in chunks],
            texts=[chunk.text for chunk in chunks],
            embeddings=vectors,
            metadatas=[
                {
                    "company_id": company_id,
                    "document_id": document_key,
                    "filename": document.original_filename,
                    "chunk_index": chunk.index,
                    "page_number": chunk.page_number or 0,
                    "source": chunk.source,
                }
                for chunk in chunks
            ],
        )
        now = datetime.now(UTC)
        document.index_status = IndexStatus.INDEXED
        document.index_error = None
        document.indexed_at = now
        document.chunk_count = len(chunks)
        document.content_hash = digest
        document.updated_at = now
        db.commit()
    except Exception as exc:
        logger.warning("Indexing failed for %s: %s", document.id, type(exc).__name__)
        _mark_failed(db, document)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The document could not be indexed",
        ) from exc

    db.refresh(document)
    logger.info("Indexed document %s into %s chunks", document.id, len(chunks))
    return _index_response(document, already_indexed=False)


def delete_index(db: Session, store: VectorStore, actor: User, document_id: UUID) -> IndexResponse:
    document, membership = _visible_document(db, actor, document_id)
    _require_manage(membership, document, actor)
    try:
        store.delete_document(str(document.company_id), str(document.id))
    except VectorStoreError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The document could not be removed from the index",
        ) from exc
    document.index_status = IndexStatus.NOT_INDEXED
    document.index_error = None
    document.chunk_count = 0
    document.content_hash = None
    document.indexed_at = None
    document.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(document)
    return _index_response(document, already_indexed=False)


def search(
    db: Session,
    embeddings: EmbeddingService,
    store: VectorStore,
    actor: User,
    *,
    company_id: UUID,
    query: str,
    document_ids: list[UUID] | None,
    top_k: int | None,
    similarity_threshold: float | None,
) -> SearchResponse:
    _require_membership(db, company_id, actor)
    _require_company_documents(db, company_id, document_ids)
    settings = get_settings()
    try:
        chunks = retrieve(
            embeddings,
            store,
            company_id=company_id,
            query=query,
            top_k=top_k or settings.rag_top_k,
            similarity_threshold=settings.rag_similarity_threshold if similarity_threshold is None else similarity_threshold,
            document_ids=document_ids,
        )
    except Exception as exc:
        logger.warning("Search failed for company %s: %s", company_id, type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The knowledge index could not be searched") from exc
    return SearchResponse(results=[_chunk_response(chunk) for chunk in chunks])


def answer_question(
    db: Session,
    embeddings: EmbeddingService,
    store: VectorStore,
    language_model: LanguageModel,
    actor: User,
    *,
    company_id: UUID,
    question: str,
    document_ids: list[UUID] | None,
    top_k: int | None,
    similarity_threshold: float | None,
) -> QueryResponse:
    found = search(
        db,
        embeddings,
        store,
        actor,
        company_id=company_id,
        query=question,
        document_ids=document_ids,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
    )
    if not found.results:
        return QueryResponse(answer=INSUFFICIENT_ANSWER, context=[], sources=[])

    context = "\n\n".join(f"[{chunk.source}]\n{chunk.text}" for chunk in found.results)
    try:
        answer = language_model.answer(question, context)
    except LanguageModelError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The language model request failed") from exc
    return QueryResponse(answer=answer, context=found.results, sources=_sources(found.results))


def _mark_failed(db: Session, document: KnowledgeDocument) -> None:
    document.index_status = IndexStatus.FAILED
    document.index_error = "The document could not be indexed"
    document.chunk_count = None
    document.updated_at = datetime.now(UTC)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Could not record the indexing failure for %s", document.id)


def _require_membership(db: Session, company_id: UUID, actor: User) -> CompanyMembership:
    membership = membership_repository.get_for_user(db, company_id, actor.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return membership


def _visible_document(db: Session, actor: User, document_id: UUID) -> tuple[KnowledgeDocument, CompanyMembership]:
    document = knowledge_repository.get(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    membership = membership_repository.get_for_user(db, document.company_id, actor.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document, membership


def _require_manage(membership: CompanyMembership, document: KnowledgeDocument, actor: User) -> None:
    if membership.role in _MANAGERS or document.uploaded_by_id == actor.id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to perform this action")


def _require_company_documents(db: Session, company_id: UUID, document_ids: list[UUID] | None) -> None:
    if not document_ids:
        return
    found = set(
        db.scalars(
            select(KnowledgeDocument.id).where(
                KnowledgeDocument.company_id == company_id,
                KnowledgeDocument.id.in_(document_ids),
            )
        ).all()
    )
    if found != set(document_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")


def _index_response(document: KnowledgeDocument, *, already_indexed: bool) -> IndexResponse:
    return IndexResponse(
        document_id=document.id,
        index_status=document.index_status,
        chunk_count=document.chunk_count,
        index_error=document.index_error,
        indexed_at=document.indexed_at,
        already_indexed=already_indexed,
    )


def _chunk_response(chunk: RetrievedChunk) -> RetrievedChunkResponse:
    return RetrievedChunkResponse(
        document_id=chunk.document_id,
        filename=chunk.filename,
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number,
        source=chunk.source,
        text=chunk.text,
        score=chunk.score,
    )


def _sources(chunks: list[RetrievedChunkResponse]) -> list[SourceDocument]:
    grouped: dict[UUID, SourceDocument] = {}
    for chunk in chunks:
        source = grouped.get(chunk.document_id)
        if source is None:
            source = SourceDocument(document_id=chunk.document_id, filename=chunk.filename, chunk_indexes=[])
            grouped[chunk.document_id] = source
        source.chunk_indexes.append(chunk.chunk_index)
    return list(grouped.values())
