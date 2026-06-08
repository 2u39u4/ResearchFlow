"""Research agent tests — critical source gate (arXiv or S2 required)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from athena.agents.research import (
    CRITICAL_SOURCES_MSG,
    CriticalResearchSourcesError,
    run_research,
)
from athena.graph.nodes import research_node
from athena.schemas.knowledge_card import KnowledgeCard


def _card(source: str) -> KnowledgeCard:
    return KnowledgeCard(
        paper_id=f"id-{source}",
        title=f"Paper from {source}",
        authors=["A Author"],
        year=2024,
        doi=f"10.1000/{source}",
        source=source,
    )


@patch("athena.agents.research.get_settings")
@patch("athena.agents.research._fetch_crossref")
@patch("athena.agents.research._fetch_semantic_scholar")
@patch("athena.agents.research._fetch_arxiv")
def test_run_research_critical_sources_both_fail(mock_arxiv, mock_s2, mock_cr, mock_settings):
    mock_settings.return_value.semantic_scholar_uses_anonymous = False
    mock_arxiv.side_effect = RuntimeError("429 arxiv")
    mock_s2.side_effect = RuntimeError("429 s2")
    mock_cr.return_value = [_card("crossref")]

    result = run_research("rag", per_source_limit=5, min_cards=1)

    assert result.critical_sources_ok is False
    assert result.errors[0] == CRITICAL_SOURCES_MSG
    assert result.sources_ok == {
        "arxiv": False,
        "semantic_scholar": False,
        "crossref": True,
    }


@patch("athena.agents.research.get_settings")
@patch("athena.agents.research._fetch_crossref")
@patch("athena.agents.research._fetch_semantic_scholar")
@patch("athena.agents.research._fetch_arxiv")
def test_run_research_critical_sources_arxiv_ok(mock_arxiv, mock_s2, mock_cr, mock_settings):
    mock_settings.return_value.semantic_scholar_uses_anonymous = False
    mock_arxiv.return_value = [_card("arxiv")]
    mock_s2.side_effect = RuntimeError("429 s2")
    mock_cr.return_value = []

    result = run_research("rag", per_source_limit=5, min_cards=1)

    assert result.critical_sources_ok is True
    assert CRITICAL_SOURCES_MSG not in result.errors


@patch("athena.agents.research.run_research")
def test_research_node_raises_when_critical_sources_fail(mock_run):
    from athena.agents.research import ResearchResult

    mock_run.return_value = ResearchResult(
        topic="rag",
        cards=[_card("crossref")],
        errors=[CRITICAL_SOURCES_MSG, "arxiv failed: x", "semantic_scholar failed: y"],
        sources_ok={"arxiv": False, "semantic_scholar": False, "crossref": True},
    )

    with pytest.raises(CriticalResearchSourcesError):
        research_node({"topic": "rag", "tasks": [], "trace": []})
