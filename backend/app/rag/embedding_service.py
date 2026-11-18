"""Embedding models. The concrete model is loaded only when an embedding is requested."""

from typing import Protocol


class EmbeddingError(Exception):
    """The embedding model could not encode text."""


class EmbeddingService(Protocol):
    model_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""

    def embed_query(self, text: str) -> list[float]:
        """Return the vector for a search query."""


class SentenceTransformerEmbeddings:
    """Local sentence-transformer model configured by EMBEDDING_MODEL."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            vectors = self._load().encode(texts, normalize_embeddings=True)
        except Exception as exc:
            raise EmbeddingError("Embeddings could not be generated") from exc
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model
