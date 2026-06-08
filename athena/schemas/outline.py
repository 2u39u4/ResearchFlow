"""Writer outline scaffolding models."""

from __future__ import annotations

from pydantic import BaseModel, Field

DEFAULT_TODO_MARKER = "[TODO: author to complete]"


class OutlineSection(BaseModel):
    heading: str
    bullets: list[str] = Field(default_factory=list)
    evidence_paper_ids: list[str] = Field(default_factory=list)


class Outline(BaseModel):
    """Structured report scaffolding — not full prose."""

    title: str
    sections: list[OutlineSection] = Field(default_factory=list)
    academic_integrity_note: str = (
        "This outline is research assistance only; authors must write and take "
        "responsibility for the final manuscript."
    )
