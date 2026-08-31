"""Embedding provider interface and similarity helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from membrane.config import MembraneConfig


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return (n, d) float32 matrix of L2-normalized embeddings."""

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).ravel()
    b = np.asarray(b, dtype=np.float32).ravel()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def pairwise_cosine(matrix: np.ndarray) -> np.ndarray:
    """Return (n, n) cosine similarity for L2-normalized or raw vectors."""
    m = np.asarray(matrix, dtype=np.float32)
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    n = m / norms
    return n @ n.T


def get_embedding_provider(config: MembraneConfig) -> EmbeddingProvider:
    if config.embeddings.provider == "sentence-transformers":
        from membrane.embeddings.sentence_transformer import SentenceTransformerProvider

        return SentenceTransformerProvider(config.embeddings.model)
    from membrane.embeddings.stub import StubEmbeddingProvider

    return StubEmbeddingProvider()
