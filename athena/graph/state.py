"""Shared graph state types (expanded in W6)."""

from __future__ import annotations

from typing import Any, TypedDict

from athena.schemas.citation import Citation, ValidationResult
from athena.schemas.knowledge_card import KnowledgeCard


class AthenaState(TypedDict, total=False):
    topic: str
    papers: list[KnowledgeCard]
    citations: list[Citation]
    validation_report: list[ValidationResult]


def state_validation_payload(results: list[ValidationResult]) -> list[dict[str, Any]]:
    return [r.model_dump() for r in results]
