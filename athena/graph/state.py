"""Shared LangGraph state for the Athena pipeline."""

from __future__ import annotations

from typing import Any, TypedDict

from athena.schemas.citation import Citation, ValidationResult
from athena.schemas.critique import Critique
from athena.schemas.knowledge_card import KnowledgeCard
from athena.schemas.outline import Outline
from athena.schemas.task import Task


class AthenaState(TypedDict, total=False):
    """Full pipeline state. Values may be models or dicts after checkpoint round-trip."""

    run_id: str
    topic: str
    constraints: dict[str, Any]
    revisions: int
    revision_log: list[dict[str, Any]]
    tasks: list[Task]
    papers: list[KnowledgeCard]
    research_errors: list[str]
    research_sources_ok: dict[str, bool]
    critiques: list[Critique]
    critic_meta: dict[str, Any]
    draft: Outline
    writer_meta: dict[str, Any]
    planner_meta: dict[str, Any]
    citations: list[Citation]
    validation_report: list[ValidationResult]
    validation_report_json: list[dict[str, Any]]
    trace: list[dict[str, Any]]


def state_validation_payload(results: list[ValidationResult]) -> list[dict[str, Any]]:
    return [r.model_dump() for r in results]
