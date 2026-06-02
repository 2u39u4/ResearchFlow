"""LangGraph-style nodes (W3: validation, W5: critic)."""

from __future__ import annotations

from typing import Any

from athena.agents.critic import run_critic
from athena.graph.state import AthenaState, state_validation_payload
from athena.schemas.citation import Citation, ValidationResult
from athena.schemas.knowledge_card import KnowledgeCard
from athena.tools.citation_validator import validate_citations


def _coerce_papers(raw: list) -> list[KnowledgeCard]:
    papers: list[KnowledgeCard] = []
    for item in raw:
        if isinstance(item, KnowledgeCard):
            papers.append(item)
        elif isinstance(item, dict):
            papers.append(KnowledgeCard.model_validate(item))
    return papers


def critic_node(state: AthenaState) -> dict[str, Any]:
    """Run Critic on topic + papers in state; write critiques list."""
    topic = (state.get("topic") or "").strip()
    papers = _coerce_papers(state.get("papers") or [])
    if not topic:
        raise ValueError("critic_node requires non-empty state['topic']")
    if not papers:
        raise ValueError("critic_node requires non-empty state['papers']")

    result = run_critic(topic, papers)
    return {
        "critiques": result.critiques,
        "critic_meta": {
            "model": result.model,
            "corpus_size": result.corpus_size,
            "evidence_grounding_rate": result.evidence_grounding_rate,
            "dropped_unsupported": result.dropped_unsupported,
            "errors": result.errors,
        },
    }


def validate_citations_node(state: AthenaState) -> dict[str, Any]:
    """
    Read citations from state, run deterministic validator, write validation_report.
    """
    raw = state.get("citations") or []
    citations: list[Citation] = []
    for item in raw:
        if isinstance(item, Citation):
            citations.append(item)
        elif isinstance(item, dict):
            citations.append(Citation.model_validate(item))

    results: list[ValidationResult] = validate_citations(citations)
    return {"validation_report": results, "validation_report_json": state_validation_payload(results)}
