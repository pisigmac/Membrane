"""Embeddings package."""

from membrane.embeddings.base import (
    EmbeddingProvider,
    cosine_similarity,
    get_embedding_provider,
    pairwise_cosine,
)

__all__ = [
    "EmbeddingProvider",
    "cosine_similarity",
    "get_embedding_provider",
    "pairwise_cosine",
]
