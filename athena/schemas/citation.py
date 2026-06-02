"""Citation input and validation result models."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

ValidationStatus = Literal["verified", "not_found", "mismatch"]


class Citation(BaseModel):
    """A bibliographic reference — any non-empty subset of fields is allowed."""

    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    doi: str = ""
    venue: str = ""

    @model_validator(mode="after")
    def at_least_one_field(self) -> "Citation":
        if not self.doi.strip() and not self.title.strip():
            raise ValueError("citation must have at least doi or title")
        return self


class ValidationResult(BaseModel):
    status: ValidationStatus
    citation: Citation
    matched_title: str = ""
    matched_doi: str = ""
    matched_authors: list[str] = Field(default_factory=list)
    matched_year: Optional[int] = None
    match_score: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)
