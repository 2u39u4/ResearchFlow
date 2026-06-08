"""Data models for the local PDF RAG module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RagChunk(BaseModel):
    """A retrievable text span extracted from an uploaded document."""

    doc_id: str
    chunk_id: str
    text: str
    page: int = 0
    char_start: int = 0
    char_end: int = 0


class RagHit(BaseModel):
    """A scored chunk returned from a similarity query."""

    chunk: RagChunk
    score: float


class RagDocument(BaseModel):
    """A parsed source document (one entry per uploaded PDF / text)."""

    doc_id: str
    source: str = ""
    pages: list[str] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(self.pages)
