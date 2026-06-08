"""
In-memory vector store with cosine similarity search.

Defaults to a NumPy brute-force index (always available, exact, fine for the
hundreds–thousands of chunks a handful of PDFs produce). A FAISS backend is used
automatically when ``use_faiss=True`` and ``faiss`` is importable.
"""

from __future__ import annotations

import numpy as np

from athena.rag.schemas import RagChunk, RagHit


class VectorStore:
    """Stores unit-norm vectors alongside their source chunks."""

    def __init__(self, dim: int, *, use_faiss: bool = False):
        self.dim = dim
        self._chunks: list[RagChunk] = []
        self._vectors: np.ndarray = np.zeros((0, dim), dtype=np.float32)
        self._faiss_index = None
        self._use_faiss = use_faiss and self._try_init_faiss(dim)

    def _try_init_faiss(self, dim: int) -> bool:
        try:
            import faiss
        except ImportError:
            return False
        self._faiss_index = faiss.IndexFlatIP(dim)
        return True

    def __len__(self) -> int:
        return len(self._chunks)

    def add(self, chunks: list[RagChunk], vectors: np.ndarray) -> None:
        if not chunks:
            return
        if vectors.shape[0] != len(chunks):
            raise ValueError("vectors and chunks length mismatch")
        if vectors.shape[1] != self.dim:
            raise ValueError(f"expected dim {self.dim}, got {vectors.shape[1]}")
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        self._chunks.extend(chunks)
        self._vectors = np.vstack([self._vectors, vectors]) if len(self._vectors) else vectors
        if self._use_faiss and self._faiss_index is not None:
            self._faiss_index.add(vectors)

    def search(self, query_vector: np.ndarray, *, top_k: int = 5) -> list[RagHit]:
        if len(self._chunks) == 0 or top_k <= 0:
            return []
        query = np.ascontiguousarray(query_vector.reshape(1, -1), dtype=np.float32)
        k = min(top_k, len(self._chunks))

        if self._use_faiss and self._faiss_index is not None:
            scores, idxs = self._faiss_index.search(query, k)
            pairs = zip(idxs[0].tolist(), scores[0].tolist())
        else:
            sims = (self._vectors @ query[0]).astype(float)
            top_idx = np.argsort(-sims)[:k]
            pairs = ((int(i), float(sims[i])) for i in top_idx)

        hits: list[RagHit] = []
        for idx, score in pairs:
            if idx < 0:
                continue
            hits.append(RagHit(chunk=self._chunks[idx], score=float(score)))
        return hits
