"""Persistent Chroma collection for company document chunks."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class VectorStoreError(Exception):
    """The vector store could not complete an operation."""


@dataclass(frozen=True)
class VectorHit:
    document_id: str
    text: str
    score: float
    metadata: dict[str, str | int | float | bool]


class VectorStore(Protocol):
    def replace_document(
        self,
        *,
        company_id: str,
        document_id: str,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str | int | float | bool]],
    ) -> None:
        """Replace every chunk stored for one document."""

    def delete_document(self, company_id: str, document_id: str) -> None:
        """Remove every chunk stored for one document."""

    def query(
        self,
        *,
        company_id: str,
        embedding: list[float],
        top_k: int,
        document_ids: list[str] | None,
    ) -> list[VectorHit]:
        """Return nearest chunks inside one company."""


class ChromaVectorStore:
    """One persistent collection. Every operation includes a company id."""

    def __init__(self, path: Path, collection_name: str) -> None:
        self.path = path
        self.collection_name = collection_name
        self._client = None

    def replace_document(
        self,
        *,
        company_id: str,
        document_id: str,
        ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, str | int | float | bool]],
    ) -> None:
        self._require_company(company_id, metadatas)
        try:
            collection = self._collection()
            self.delete_document(company_id, document_id)
            collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError("The vector store could not save the document") from exc

    def delete_document(self, company_id: str, document_id: str) -> None:
        try:
            collection = self._collection()
            existing = collection.get(
                where={"$and": [{"company_id": company_id}, {"document_id": document_id}]},
                include=[],
            )
            identifiers = existing.get("ids") or []
            if identifiers:
                collection.delete(ids=identifiers)
        except Exception as exc:
            raise VectorStoreError("The vector store could not delete the document") from exc

    def query(
        self,
        *,
        company_id: str,
        embedding: list[float],
        top_k: int,
        document_ids: list[str] | None,
    ) -> list[VectorHit]:
        where: dict[str, object] = {"company_id": company_id}
        if document_ids:
            where = {"$and": [{"company_id": company_id}, {"document_id": {"$in": document_ids}}]}
        try:
            collection = self._collection()
            if collection.count() == 0:
                return []
            result = collection.query(
                query_embeddings=[embedding],
                n_results=min(top_k, collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreError("The vector store could not be searched") from exc
        return _hits(result)

    def close(self) -> None:
        client = self._client
        self._client = None
        if client is not None and hasattr(client, "close"):
            client.close()

    def _collection(self):
        if self._client is None:
            import chromadb
            from chromadb.config import Settings

            self.path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(self.path),
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _require_company(company_id: str, metadatas: list[dict[str, str | int | float | bool]]) -> None:
        if any(item.get("company_id") != company_id for item in metadatas):
            raise VectorStoreError("Refusing to store a chunk outside its company")


def _hits(result: dict) -> list[VectorHit]:
    documents = (result.get("documents") or [[]])[0] or []
    metadatas = (result.get("metadatas") or [[]])[0] or []
    distances = (result.get("distances") or [[]])[0] or []
    hits: list[VectorHit] = []
    for text, metadata, distance in zip(documents, metadatas, distances, strict=False):
        if not text or not metadata:
            continue
        similarity = max(0.0, min(1.0, 1.0 - float(distance)))
        hits.append(
            VectorHit(
                document_id=str(metadata.get("document_id", "")),
                text=text,
                score=similarity,
                metadata=metadata,
            )
        )
    return hits
