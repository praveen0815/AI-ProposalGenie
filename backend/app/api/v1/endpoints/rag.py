"""Indexing and semantic search routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_embedding_service, get_language_model, get_vector_store
from app.models.enums import DocumentProcessingStatus
from app.models.user import User
from app.rag.embedding_service import EmbeddingService
from app.rag.llm import LanguageModel
from app.rag.rag_service import answer_question, delete_index, index_document
from app.rag.rag_service import search as search_documents
from app.rag.vector_store import VectorStore
from app.schemas.rag import IndexResponse, QueryRequest, QueryResponse, SearchRequest, SearchResponse
from app.services import documents as document_service

router = APIRouter()


@router.post("/index/document/{document_id}", response_model=IndexResponse)
def index_one_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    store: VectorStore = Depends(get_vector_store),
) -> IndexResponse:
    return index_document(db, embeddings, store, current_user, document_id, force=False)


@router.post("/reindex/document/{document_id}", response_model=IndexResponse)
def reindex_one_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    store: VectorStore = Depends(get_vector_store),
) -> IndexResponse:
    return index_document(db, embeddings, store, current_user, document_id, force=True)


@router.delete("/index/document/{document_id}", response_model=IndexResponse)
def delete_one_index(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    store: VectorStore = Depends(get_vector_store),
) -> IndexResponse:
    return delete_index(db, store, current_user, document_id)


@router.post("/search", response_model=SearchResponse)
def search(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    store: VectorStore = Depends(get_vector_store),
) -> SearchResponse:
    return search_documents(
        db,
        embeddings,
        store,
        current_user,
        company_id=payload.company_id,
        query=payload.query,
        document_ids=payload.document_ids,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
    )


@router.post("/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    store: VectorStore = Depends(get_vector_store),
    language_model: LanguageModel = Depends(get_language_model),
) -> QueryResponse:
    return answer_question(
        db,
        embeddings,
        store,
        language_model,
        current_user,
        company_id=payload.company_id,
        question=payload.question,
        document_ids=payload.document_ids,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
    )


def index_after_processing(
    db: Session,
    embeddings: EmbeddingService,
    store: VectorStore,
    actor: User,
    document_id: UUID,
) -> None:
    """Index a freshly extracted document without failing the upload."""

    document = document_service.get_document(db, actor, document_id)
    if document.processing_status != DocumentProcessingStatus.COMPLETED:
        try:
            delete_index(db, store, actor, document_id)
        except HTTPException:
            return
        return
    try:
        index_document(db, embeddings, store, actor, document_id, force=True)
    except HTTPException:
        return
