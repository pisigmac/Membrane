"""Deterministic hash-based embeddings for tests and offline use."""

from __future__ import annotations

import hashlib

import numpy as np

from membrane.embeddings.base import EmbeddingProvider

DIM = 64


class StubEmbeddingProvider(EmbeddingProvider):
    """Maps text to a stable pseudo-embedding via token hashing."""

    def __init__(self, dim: int = DIM) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            out[i] = self._vector(text)
        return out

    def _vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = text.lower().split()
        if not tokens:
            tokens = [""]
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            # Use multiple bytes to set several dimensions
            for j in range(0, min(len(digest), self.dim)):
                vec[j % self.dim] += (digest[j] / 255.0) - 0.5
            # Also hash bigrams for slightly richer similarity
        for a, b in zip(tokens, tokens[1:]):
            digest = hashlib.md5(f"{a}_{b}".encode("utf-8")).digest()
            idx = digest[0] % self.dim
            vec[idx] += 0.35
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec
