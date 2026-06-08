"""Local PDF RAG: parse, chunk, embed, and search uploaded documents.

Uploaded PDFs stay on the local machine and are never sent to scholarly APIs.
This module complements the public Research agent with optional private context.
"""

from __future__ import annotations

from athena.rag.chunking import chunk_document, chunk_text, normalize_whitespace
from athena.rag.embeddings import (
    Embedder,
    HashingEmbedder,
    SentenceTransformerEmbedder,
    get_embedder,
)
from athena.rag.index import PdfRagIndex
from athena.rag.pdf import (
    document_from_bytes,
    document_from_text,
    extract_pdf_pages,
    load_pdf_document,
)
from athena.rag.schemas import RagChunk, RagDocument, RagHit
from athena.rag.store import VectorStore

__all__ = [
    "PdfRagIndex",
    "VectorStore",
    "RagChunk",
    "RagDocument",
    "RagHit",
    "Embedder",
    "HashingEmbedder",
    "SentenceTransformerEmbedder",
    "get_embedder",
    "chunk_text",
    "chunk_document",
    "normalize_whitespace",
    "extract_pdf_pages",
    "load_pdf_document",
    "document_from_bytes",
    "document_from_text",
]
