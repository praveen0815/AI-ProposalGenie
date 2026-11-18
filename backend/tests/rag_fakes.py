"""Deterministic stand-ins for the embedding model and language model."""

import hashlib
import math
import re


class HashEmbeddingService:
    """Bag-of-words vectors so tests can check relevance without downloading a model."""

    model_name = "hash-test"
    dimensions = 64

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        if not tokens:
            vector[0] = 1.0
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            vector[digest[0] % self.dimensions] += 1.0 if digest[1] % 2 == 0 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class FakeLanguageModel:
    def __init__(self) -> None:
        self.calls = 0

    def answer(self, question: str, context: str) -> str:
        self.calls += 1
        if not context.strip():
            return "I don't have enough information in the company documents to answer that."
        return "Based on the company documents, the retrieved context answers the question."
