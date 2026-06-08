"""LangGraph nodes: Planner → Research → Critic → Writer → Validator (+ revise loop)."""

from __future__ import annotations

import uuid
from typing import Any

from athena.agents.critic import run_critic, supported_only
from athena.agents.planner import run_planner
from athena.agents.research import CriticalResearchSourcesError, run_research
from athena.agents.writer import run_writer
from athena.config import get_settings
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


def _search_queries(state: AthenaState, topic: str) -> list[str]:
    """All distinct search-task queries from the plan (primary first), so the plan
    materially drives retrieval. Falls back to the topic when the plan has none."""
    queries: list[str] = []
    for task in _coerce_tasks(state.get("tasks") or []):
        if task.type == "search":
            q = task.query.strip()
            if q and q not in queries:
                queries.append(q)
    if not queries:
        queries = [topic]
    return queries


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


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def research_node(state: AthenaState) -> dict[str, Any]:
    topic = (state.get("topic") or "").strip()
    queries = _search_queries(state, topic)
    primary = queries[0]
    constraints = state.get("constraints") or {}
    per_source = int(constraints.get("per_source_limit", 15))
    min_cards = int(constraints.get("min_cards", 10))
    year_min = _int_or_none(constraints.get("year_min"))
    year_max = _int_or_none(constraints.get("year_max"))

    # Domain (when provided) becomes an extra, more specific retrieval query.
    extra_queries = queries[1:]
    domain = str(constraints.get("domain") or "").strip()
    if domain:
        extra_queries = [*extra_queries, f"{primary} {domain}"]

    # On a revision pass, broaden retrieval to recover from the diagnosed failure.
    revisions = int(state.get("revisions") or 0)
    if revisions > 0:
        per_source = min(per_source + 5 * revisions, 50)
        min_cards = min_cards + 2 * revisions
    # "research_relax": coverage shortfall — widen further and drop the year filter.
    if state.get("repair_action") == "research_relax":
        per_source = min(per_source + 10, 50)
        year_min = year_max = None

    result = run_research(
        primary,
        arxiv_query=topic,
        fallback_topic=topic if primary != topic else None,
        per_source_limit=per_source,
        min_cards=min_cards,
        extra_queries=extra_queries,
        year_min=year_min,
        year_max=year_max,
    )
    if not result.critical_sources_ok:
        raise CriticalResearchSourcesError(result.errors)

    update: dict[str, Any] = {
        "papers": result.cards,
        "research_errors": result.errors,
        "research_sources_ok": result.sources_ok,
    }
    merged = {**state, **update}
    all_queries = [primary, *extra_queries]
    update.update(
        append_trace(
            merged,
            step="research",
            agent="research",
            summary=f"{len(result.cards)} papers ({len(all_queries)} plan queries)",
            payload={
                "errors": result.errors,
                "count": len(result.cards),
                "queries": all_queries,
                "year_range": [year_min, year_max],
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


def _unverified_ratio(results: list[ValidationResult]) -> float:
    if not results:
        return 0.0
    unverified = sum(1 for r in results if r.status != "verified")
    return unverified / len(results)


# Repair actions the controller can choose, and the node each routes to.
_ACTION_ROUTES = {
    "research_broaden": "research",  # too many unverified citations -> wider retrieval
    "research_relax": "research",  # too few papers -> relax filters + wider retrieval
    "recritique": "critic",  # weak evidence grounding -> re-run the Critic
    "finish": "finish",
}


def diagnose_repair(state: AthenaState) -> tuple[str, dict[str, Any]]:
    """Inspect the run and choose a repair action (the controller's policy).

    Returns (action, diagnosis). Priority: unresolved citations > too few papers >
    weak evidence grounding. Returns 'finish' when nothing needs repair or the
    revision budget is exhausted.
    """
    constraints = state.get("constraints") or {}
    settings = get_settings()
    max_revisions = int(constraints.get("max_revisions", settings.max_revisions))
    fake_threshold = float(
        constraints.get("revision_fake_threshold", settings.revision_fake_threshold)
    )
    grounding_threshold = float(
        constraints.get("revision_grounding_threshold", settings.revision_grounding_threshold)
    )
    min_cards = int(constraints.get("min_cards", 10))

    raw = state.get("validation_report") or []
    results = [
        r if isinstance(r, ValidationResult) else ValidationResult.model_validate(r) for r in raw
    ]
    ratio = _unverified_ratio(results)
    paper_count = len(state.get("papers") or [])
    grounding = (state.get("critic_meta") or {}).get("evidence_grounding_rate")

    diagnosis = {
        "unverified_ratio": round(ratio, 3),
        "paper_count": paper_count,
        "evidence_grounding_rate": grounding,
    }

    revisions = int(state.get("revisions") or 0)
    if revisions >= max_revisions:
        return "finish", diagnosis
    if results and ratio > fake_threshold:
        return "research_broaden", diagnosis
    if paper_count < min_cards:
        return "research_relax", diagnosis
    if grounding is not None and grounding < grounding_threshold:
        return "recritique", diagnosis
    return "finish", diagnosis


def controller_node(state: AthenaState) -> dict[str, Any]:
    """Diagnose the run and pick a repair action (re-research / re-critique / finish).

    This is the agent's decision point: rather than a fixed straight-line DAG, the
    controller reads validation, coverage, and grounding signals and routes to the
    repair that matches the dominant failure mode, bounded by ``max_revisions``.
    """
    action, diagnosis = diagnose_repair(state)
    update: dict[str, Any] = {"repair_action": action}
    if action == "finish":
        return update

    revisions = int(state.get("revisions") or 0) + 1
    entry = {"revision": revisions, "action": action, **diagnosis}
    revision_log = list(state.get("revision_log") or [])
    revision_log.append(entry)
    update["revisions"] = revisions
    update["revision_log"] = revision_log

    reason = {
        "research_broaden": f"{diagnosis['unverified_ratio']:.0%} citations unverified",
        "research_relax": f"only {diagnosis['paper_count']} papers",
        "recritique": f"grounding {diagnosis['evidence_grounding_rate']}",
    }.get(action, "")
    merged = {**state, **update}
    update.update(
        append_trace(
            merged,
            step="controller",
            agent="controller",
            summary=f"revision {revisions}: {reason} → {action}",
            payload=entry,
        )
    )
    return update


def route_after_controller(state: AthenaState) -> str:
    """Conditional edge: map the controller's chosen action to the next node."""
    return _ACTION_ROUTES.get(state.get("repair_action") or "finish", "finish")
