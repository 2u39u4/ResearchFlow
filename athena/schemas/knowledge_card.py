"""Structured paper card — metadata fields must come from API converters only."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceName = Literal["arxiv", "semantic_scholar", "crossref"]


class KnowledgeCard(BaseModel):
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: str = ""
    doi: str = ""
    url: str = ""
    abstract: str = ""
    contributions: list[str] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    source: SourceName
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def metadata_richness(self) -> int:
        """Higher score = more complete metadata (for merge preference)."""
        score = 0
        if self.doi:
            score += 4
        if self.abstract:
            score += 2
        if self.authors:
            score += 1
        if self.year:
            score += 1
        if self.venue:
            score += 1
        return score
