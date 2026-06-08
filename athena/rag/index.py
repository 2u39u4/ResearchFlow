"""High-level PDF RAG index: parse -> chunk -> embed -> search."""

from __future__ import annotations

from pathlib import Path

from athena.config import Settings, get_settings
from athena.rag.chunking import chunk_document
from athena.rag.embeddings import Embedder, get_embedder
from athena.rag.pdf import document_from_bytes, document_from_text, load_pdf_document
from athena.rag.schemas import RagChunk, RagDocument, RagHit
from athena.rag.store import VectorStore


class PdfRagIndex:
    """A queryable index over uploaded documents (PDF or plain text).

    Designed for *private* context: uploaded PDFs never leave the machine and are
    not sent to scholarly APIs. Retrieval here complements (does not replace) the
    public multi-source Research agent.
    """

    def __init__(
        self,
        *,
        embedder: Embedder | None = None,
        settings: Settings | None = None,
        chunk_size: int | None = None,
        overlap: int | None = None,
        use_faiss: bool | None = None,
    ):
        self.settings = settings or get_settings()
        self.embedder = embedder or get_embedder(
            self.settings.rag_embedding_backend,
            dim=self.settings.rag_embedding_dim,
            model_name=self.settings.rag_st_model,
        )
        self.chunk_size = chunk_size if chunk_size is not None else self.settings.rag_chunk_size
        self.overlap = overlap if overlap is not None else self.settings.rag_chunk_overlap
        use_faiss = self.settings.rag_use_faiss if use_faiss is None else use_faiss
        self.store = VectorStore(self.embedder.dim, use_faiss=use_faiss)
        self._doc_ids: list[str] = []

    @property
    def doc_ids(self) -> list[str]:
        return list(self._doc_ids)

    @property
    def chunk_count(self) -> int:
        return len(self.store)

    def add_document(self, doc: RagDocument) -> int:
        """Chunk, embed, and index a document. Returns the number of chunks added."""
        chunks: list[RagChunk] = chunk_document(
            doc, chunk_size=self.chunk_size, overlap=self.overlap
        )
        if not chunks:
            return 0
        vectors = self.embedder.embed([c.text for c in chunks])
        self.store.add(chunks, vectors)
        if doc.doc_id not in self._doc_ids:
            self._doc_ids.append(doc.doc_id)
        return len(chunks)

    def add_pdf_bytes(self, data: bytes, *, doc_id: str, source: str = "") -> int:
        return self.add_document(document_from_bytes(data, doc_id=doc_id, source=source))

    def add_pdf_path(self, path: Path | str, *, doc_id: str | None = None) -> int:
        return self.add_document(load_pdf_document(path, doc_id=doc_id))

    def add_text(self, text: str, *, doc_id: str, source: str = "") -> int:
        return self.add_document(document_from_text(text, doc_id=doc_id, source=source))

    def query(self, text: str, *, top_k: int = 5) -> list[RagHit]:
        if not text.strip() or self.chunk_count == 0:
            return []
        query_vec = self.embedder.embed([text])[0]
        return self.store.search(query_vec, top_k=top_k)
