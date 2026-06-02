"""Critic output models — evidence-grounded claims only."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

CritiqueType = Literal["gap", "weakness", "novelty"]
CritiqueStatus = Literal["supported", "unsupported"]


class Critique(BaseModel):
    """A single critical insight tied to retrieved papers."""

    claim: str = Field(min_length=1)
    type: CritiqueType
    evidence_paper_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    status: CritiqueStatus = "supported"
    notes: str = ""  # e.g. why marked unsupported

    @field_validator("claim")
    @classmethod
    def strip_claim(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("claim must be non-empty")
        return s


class CritiqueBatch(BaseModel):
    """LLM structured response wrapper."""

    critiques: list[Critique] = Field(default_factory=list)
