"""Deterministic text chunking for RAG indexing."""

from __future__ import annotations

import re

from athena.rag.schemas import RagChunk, RagDocument

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def chunk_text(
    text: str,
    *,
    chunk_size: int = 800,
    overlap: int = 150,
) -> list[tuple[str, int, int]]:
    """
    Split text into overlapping windows.

    Returns (chunk_text, char_start, char_end) triples over the *normalized* text.
    Chunking is character-based so it is deterministic and dependency-free.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")

    cleaned = normalize_whitespace(text)
    if not cleaned:
        return []

    step = chunk_size - overlap
    out: list[tuple[str, int, int]] = []
    start = 0
    n = len(cleaned)
    while start < n:
        end = min(start + chunk_size, n)
        out.append((cleaned[start:end], start, end))
        if end >= n:
            break
        start += step
    return out


def chunk_document(
    doc: RagDocument,
    *,
    chunk_size: int = 800,
    overlap: int = 150,
) -> list[RagChunk]:
    """Chunk each page of a document so hits keep their page number."""
    chunks: list[RagChunk] = []
    for page_no, page_text in enumerate(doc.pages or [doc.text]):
        for triple in chunk_text(page_text, chunk_size=chunk_size, overlap=overlap):
            span, c0, c1 = triple
            chunk_id = f"{doc.doc_id}:p{page_no}:{c0}"
            chunks.append(
                RagChunk(
                    doc_id=doc.doc_id,
                    chunk_id=chunk_id,
                    text=span,
                    page=page_no,
                    char_start=c0,
                    char_end=c1,
                )
            )
    return chunks
