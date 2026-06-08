"""LangGraph nodes: Planner → Research → Critic → Writer → Validator."""

from __future__ import annotations

import uuid
from typing import Any

from athena.agents.critic import run_critic, supported_only
from athena.agents.planner import run_planner
from athena.agents.research import CriticalResearchSourcesError, run_research
from athena.agents.writer import run_writer
from athena.graph.citations_from_corpus import build_citations_for_validation
from athena.graph.state import AthenaState, state_validation_payload
from athena.graph.tracing import append_trace
from athena.schemas.citation import Citation, ValidationResult
from athena.schemas.critique import Critique
from athena.schemas.knowledge_card import KnowledgeCard
from athena.schemas.outline import Outline
from athena.schemas.task import Task
from athena.tools.citation_validator import validate_citations


def _coerce_papers(raw: list) -> list[KnowledgeCard]:
    papers: list[KnowledgeCard] = []
    for item in raw:
        if isinstance(item, KnowledgeCard):
            papers.append(item)
        elif isinstance(item, dict):
            papers.append(KnowledgeCard.model_validate(item))
    return papers


def _coerce_tasks(raw: list) -> list[Task]:
    tasks: list[Task] = []
    for item in raw:
        if isinstance(item, Task):
            tasks.append(item)
        elif isinstance(item, dict):
            tasks.append(Task.model_validate(item))
    return tasks


def _coerce_critiques(raw: list) -> list[Critique]:
    out: list[Critique] = []
    for item in raw:
        if isinstance(item, Critique):
            out.append(item)
        elif isinstance(item, dict):
            out.append(Critique.model_validate(item))
    return out


def _coerce_outline(raw: Outline | dict | None) -> Outline | None:
    if raw is None:
        return None
    if isinstance(raw, Outline):
        return raw
    return Outline.model_validate(raw)


def _search_query(state: AthenaState, topic: str) -> str:
    for task in _coerce_tasks(state.get("tasks") or []):
        if task.type == "search" and task.query.strip():
            return task.query.strip()
    return topic


def planner_node(state: AthenaState) -> dict[str, Any]:
    topic = (state.get("topic") or "").strip()
    if not topic:
        raise ValueError("planner_node requires state['topic']")

    result = run_planner(topic)
    update: dict[str, Any] = {
        "run_id": state.get("run_id") or str(uuid.uuid4()),
        "tasks": result.plan.tasks,
        "planner_meta": {
            "model": result.model,
            "used_fallback": result.used_fallback,
            "errors": result.errors,
        },
    }
    update.update(
        append_trace(
            state,
            step="planner",
            agent="planner",
            summary=f"{len(result.plan.tasks)} tasks (fallback={result.used_fallback})",
            payload={"tasks": [t.model_dump() for t in result.plan.tasks]},
        )
    )
    return update


def research_node(state: AthenaState) -> dict[str, Any]:
    topic = (state.get("topic") or "").strip()
    query = _search_query(state, topic)
    constraints = state.get("constraints") or {}
    per_source = int(constraints.get("per_source_limit", 15))
    min_cards = int(constraints.get("min_cards", 10))

    result = run_research(
        query,
        arxiv_query=topic,
        fallback_topic=topic if query != topic else None,
        per_source_limit=per_source,
        min_cards=min_cards,
    )
    if not result.critical_sources_ok:
        raise CriticalResearchSourcesError(result.errors)

    update: dict[str, Any] = {
        "papers": result.cards,
        "research_errors": result.errors,
        "research_sources_ok": result.sources_ok,
    }
    merged = {**state, **update}
    update.update(
        append_trace(
            merged,
            step="research",
            agent="research",
            summary=f"{len(result.cards)} papers (query={query!r})",
            payload={
                "errors": result.errors,
                "count": len(result.cards),
                "sources_ok": result.sources_ok,
            },
        )
    )
    return update


def critic_node(state: AthenaState) -> dict[str, Any]:
    topic = (state.get("topic") or "").strip()
    papers = _coerce_papers(state.get("papers") or [])
    if not topic:
        raise ValueError("critic_node requires state['topic']")
    if not papers:
        raise ValueError("critic_node requires state['papers']")

    result = run_critic(topic, papers)
    update: dict[str, Any] = {
        "critiques": result.critiques,
        "critic_meta": {
            "model": result.model,
            "corpus_size": result.corpus_size,
            "evidence_grounding_rate": result.evidence_grounding_rate,
            "dropped_unsupported": result.dropped_unsupported,
            "errors": result.errors,
        },
    }
    merged = {**state, **update}
    update.update(
        append_trace(
            merged,
            step="critic",
            agent="critic",
            summary=(
                f"{len(supported_only(result.critiques))} supported / "
                f"{len(result.critiques)} critiques"
            ),
            payload={"critic_meta": update["critic_meta"]},
        )
    )
    return update


def writer_node(state: AthenaState) -> dict[str, Any]:
    topic = (state.get("topic") or "").strip()
    papers = _coerce_papers(state.get("papers") or [])
    critiques = _coerce_critiques(state.get("critiques") or [])
    if not papers:
        raise ValueError("writer_node requires state['papers']")

    result = run_writer(topic, papers, critiques)
    update: dict[str, Any] = {
        "draft": result.outline,
        "writer_meta": {
            "model": result.model,
            "used_fallback": result.used_fallback,
            "errors": result.errors,
        },
    }
    merged = {**state, **update}
    update.update(
        append_trace(
            merged,
            step="writer",
            agent="writer",
            summary=f"outline '{result.outline.title}' ({len(result.outline.sections)} sections)",
            payload={"used_fallback": result.used_fallback},
        )
    )
    return update


def prepare_citations_node(state: AthenaState) -> dict[str, Any]:
    papers = _coerce_papers(state.get("papers") or [])
    critiques = _coerce_critiques(state.get("critiques") or [])
    outline = _coerce_outline(state.get("draft"))

    citations = build_citations_for_validation(papers, critiques, outline)
    update: dict[str, Any] = {"citations": citations}
    merged = {**state, **update}
    update.update(
        append_trace(
            merged,
            step="prepare_citations",
            agent="validator",
            summary=f"{len(citations)} citations queued for validation",
            payload={"paper_ids": [c.doi or c.title for c in citations]},
        )
    )
    return update


def validate_citations_node(state: AthenaState) -> dict[str, Any]:
    raw = state.get("citations") or []
    citations: list[Citation] = []
    for item in raw:
        if isinstance(item, Citation):
            citations.append(item)
        elif isinstance(item, dict):
            citations.append(Citation.model_validate(item))

    results: list[ValidationResult] = validate_citations(citations)
    update: dict[str, Any] = {
        "validation_report": results,
        "validation_report_json": state_validation_payload(results),
    }
    verified = sum(1 for r in results if r.status == "verified")
    merged = {**state, **update}
    update.update(
        append_trace(
            merged,
            step="validator",
            agent="validator",
            summary=f"{verified}/{len(results)} citations verified",
            payload={"validation_report_json": update["validation_report_json"]},
        )
    )
    return update
