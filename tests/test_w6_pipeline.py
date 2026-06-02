"""W6 pipeline tests — graph compile, trace, citations, mocked agents."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from athena.agents.planner import default_task_plan, run_planner
from athena.agents.writer import fallback_outline
from athena.graph.build_graph import build_athena_graph, initial_state
from athena.graph.citations_from_corpus import build_citations_for_validation, collect_paper_ids
from athena.graph.nodes import planner_node, prepare_citations_node, research_node
from athena.graph.report import state_to_report
from athena.graph.tracing import append_trace
from athena.schemas.critique import Critique
from athena.schemas.knowledge_card import KnowledgeCard
from athena.schemas.outline import DEFAULT_TODO_MARKER, Outline, OutlineSection
from athena.schemas.task import TaskPlan
from langgraph.checkpoint.memory import MemorySaver


def _card(pid: str) -> KnowledgeCard:
    return KnowledgeCard(
        paper_id=pid,
        title=f"Title {pid}",
        authors=["A Author"],
        year=2024,
        doi=f"10.1000/{pid}",
        abstract="Abstract text.",
        source="arxiv",
    )


def test_default_task_plan():
    plan = default_task_plan("graph rag")
    assert len(plan.tasks) >= 4
    assert plan.tasks[0].type == "search"
    assert plan.tasks[0].query == "graph rag"


def test_append_trace():
    state = {"trace": []}
    out = append_trace(state, step="planner", agent="planner", summary="ok")
    assert len(out["trace"]) == 1
    assert out["trace"][0]["step"] == "planner"


def test_collect_paper_ids_from_critiques():
    papers = [_card("a:1"), _card("a:2")]
    critiques = [
        Critique(claim="gap", type="gap", evidence_paper_ids=["a:1"], confidence=0.8)
    ]
    outline = Outline(
        title="T",
        sections=[OutlineSection(heading="S", evidence_paper_ids=["a:2"])],
    )
    ids = collect_paper_ids(papers, critiques, outline)
    assert ids == ["a:1", "a:2"]


def test_build_citations_for_validation():
    papers = [_card("a:1")]
    citations = build_citations_for_validation(papers, [], None)
    assert len(citations) == 1
    assert citations[0].doi


def test_fallback_outline_has_todo():
    outline = fallback_outline("topic", [], [_card("a:1")])
    bullets = [b for s in outline.sections for b in s.bullets]
    assert any(DEFAULT_TODO_MARKER in b for b in bullets)


def test_build_graph_compiles():
    graph = build_athena_graph(checkpointer=MemorySaver(), use_sqlite=False)
    assert graph is not None


@patch("athena.agents.planner.LLMClient")
def test_planner_fallback(mock_cls):
    mock_cls.return_value.chat.side_effect = RuntimeError("api down")
    result = run_planner("test topic", llm=mock_cls.return_value)
    assert result.used_fallback
    assert len(result.plan.tasks) >= 3


@patch("athena.graph.nodes.run_research")
def test_research_node(mock_research):
    from athena.agents.research import ResearchResult

    mock_research.return_value = ResearchResult(
        topic="rag",
        cards=[_card("a:1")],
        errors=[],
    )
    out = research_node(
        {
            "topic": "rag",
            "tasks": default_task_plan("rag").tasks,
            "trace": [],
        }
    )
    assert len(out["papers"]) == 1
    assert len(out["trace"]) == 1


@patch("athena.graph.nodes.run_planner")
@patch("athena.graph.nodes.run_research")
@patch("athena.graph.nodes.run_critic")
@patch("athena.graph.nodes.run_writer")
@patch("athena.graph.nodes.validate_citations")
def test_pipeline_invoke_mocked(
    mock_validate,
    mock_writer,
    mock_critic,
    mock_research,
    mock_planner,
):
    from athena.agents.critic import CriticResult
    from athena.agents.planner import PlannerResult
    from athena.agents.research import ResearchResult
    from athena.agents.writer import WriterResult
    from athena.schemas.citation import ValidationResult

    mock_planner.return_value = PlannerResult(
        topic="rag",
        plan=default_task_plan("rag"),
        model="gpt-5.5",
        used_fallback=True,
        errors=[],
    )
    mock_research.return_value = ResearchResult(
        topic="rag",
        cards=[_card("a:1"), _card("a:2")],
        errors=[],
    )
    mock_critic.return_value = CriticResult(
        topic="rag",
        corpus_size=2,
        critiques=[
            Critique(
                claim="Among the 2 retrieved papers, gap.",
                type="gap",
                evidence_paper_ids=["a:1"],
                confidence=0.8,
            )
        ],
        dropped_unsupported=0,
        evidence_grounding_rate=1.0,
        model="gpt-5.5",
        errors=[],
    )
    mock_writer.return_value = WriterResult(
        topic="rag",
        outline=Outline(
            title="Outline",
            sections=[
                OutlineSection(
                    heading="Intro",
                    bullets=[DEFAULT_TODO_MARKER],
                    evidence_paper_ids=["a:1"],
                )
            ],
        ),
        model="gpt-5.5",
        used_fallback=False,
        errors=[],
    )
    mock_validate.return_value = [
        ValidationResult(status="verified", citation=build_citations_for_validation([_card("a:1")], [], None)[0])
    ]

    graph = build_athena_graph(checkpointer=MemorySaver(), use_sqlite=False)
    final = graph.invoke(
        initial_state("rag", constraints={"min_cards": 2, "per_source_limit": 5}),
        config={"configurable": {"thread_id": "test-thread-1"}},
    )
    report = state_to_report(final)
    assert report["topic"] == "rag"
    assert len(report["papers"]) == 2
    assert len(report["trace"]) >= 5
    assert report["draft"] is not None
    assert len(report["validation_report"]) >= 1


def test_prepare_citations_node():
    papers = [_card("a:1")]
    critiques = [
        Critique(claim="g", type="gap", evidence_paper_ids=["a:1"], confidence=0.7)
    ]
    out = prepare_citations_node(
        {
            "papers": papers,
            "critiques": critiques,
            "draft": Outline(title="T", sections=[]),
            "trace": [],
        }
    )
    assert len(out["citations"]) == 1
