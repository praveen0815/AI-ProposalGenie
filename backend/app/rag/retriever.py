"""Company-scoped semantic retrieval."""

from dataclasses import dataclass
from uuid import UUID

from app.rag.embedding_service import EmbeddingService
from app.rag.vector_store import VectorStore


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: UUID
    filename: str
    chunk_index: int
    page_number: int | None
    source: str
    text: str
    score: float


def retrieve(
    embeddings: EmbeddingService,
    store: VectorStore,
    *,
    company_id: UUID,
    query: str,
    top_k: int,
    similarity_threshold: float,
    document_ids: list[UUID] | None,
) -> list[RetrievedChunk]:
    """Search one company and drop matches below the similarity threshold."""

    vector = embeddings.embed_query(query)
    allowed = [str(document_id) for document_id in document_ids] if document_ids else None
    hits = store.query(company_id=str(company_id), embedding=vector, top_k=top_k, document_ids=allowed)
    chunks: list[RetrievedChunk] = []
    for hit in hits:
        if hit.score < similarity_threshold or not hit.document_id:
            continue
        page_number = hit.metadata.get("page_number")
        page = page_number if isinstance(page_number, int) and page_number > 0 else None
        chunk_index = hit.metadata.get("chunk_index")
        chunks.append(
            RetrievedChunk(
                document_id=UUID(hit.document_id),
                filename=str(hit.metadata.get("filename") or "document"),
                chunk_index=int(chunk_index) if isinstance(chunk_index, int) else 0,
                page_number=page,
                source=str(hit.metadata.get("source") or hit.metadata.get("filename") or "document"),
                text=hit.text,
                score=round(hit.score, 4),
            )
        )
    return chunks
