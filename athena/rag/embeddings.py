"""
Embedding backends for the local RAG module.

Two backends are provided:

* ``HashingEmbedder`` (default) — a dependency-free, deterministic feature-hashing
  bag-of-words encoder. It needs no model download and produces stable vectors,
  which keeps unit tests and CI fast and offline.
* ``SentenceTransformerEmbedder`` (optional) — wraps ``sentence-transformers`` for
  higher-quality semantic embeddings. Imported lazily so it is only required when
  explicitly selected (``ATHENA_RAG_EMBEDDING_BACKEND=sentence-transformers``).
"""

from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    """Maps a batch of texts to an (n, dim) float32 matrix of unit vectors."""

    dim: int

    def embed(self, texts: list[str]) -> np.ndarray: ...


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


class HashingEmbedder:
    """Deterministic feature-hashing encoder (no external model)."""

    def __init__(self, dim: int = 256, *, ngram: int = 2):
        if dim <= 0:
            raise ValueError("dim must be positive")
        if ngram < 1:
            raise ValueError("ngram must be >= 1")
        self.dim = dim
        self.ngram = ngram

    def _hash(self, token: str) -> tuple[int, float]:
        digest = hashlib.md5(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "little") % self.dim
        sign = 1.0 if digest[4] & 1 else -1.0
        return idx, sign

    def _features(self, text: str) -> list[str]:
        tokens = _tokenize(text)
        feats = list(tokens)
        for k in range(2, self.ngram + 1):
            feats.extend(" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1))
        return feats

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for feat in self._features(text):
                idx, sign = self._hash(feat)
                vectors[row, idx] += sign
        return _l2_normalize(vectors)


class SentenceTransformerEmbedder:
    """Semantic embeddings via sentence-transformers (lazy, optional dependency)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise ImportError(
                "sentence-transformers is not installed. Install the optional extra: "
                "pip install 'athena-research-assistant[rag]'"
            ) from exc
        self._model = SentenceTransformer(model_name)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vectors = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


def get_embedder(
    backend: str = "hashing",
    *,
    dim: int = 256,
    model_name: str = "all-MiniLM-L6-v2",
) -> Embedder:
    """Factory selecting an embedding backend by name."""
    normalized = (backend or "hashing").strip().lower()
    if normalized in {"sentence-transformers", "sentence_transformers", "st"}:
        return SentenceTransformerEmbedder(model_name=model_name)
    if normalized == "hashing":
        return HashingEmbedder(dim=dim)
    raise ValueError(f"unknown embedding backend: {backend!r}")
