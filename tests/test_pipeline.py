"""Pipeline tests — graph compile, trace, citations, mocked agents."""

from __future__ import annotations

from unittest.mock import patch

from langgraph.checkpoint.memory import MemorySaver

from athena.agents.planner import default_task_plan, run_planner
from athena.agents.writer import fallback_outline
from athena.graph.build_graph import build_athena_graph, initial_state
from athena.graph.citations_from_corpus import build_citations_for_validation, collect_paper_ids
from athena.graph.nodes import prepare_citations_node, research_node
from athena.graph.report import state_to_report
from athena.graph.tracing import append_trace
from athena.schemas.critique import Critique
from athena.schemas.knowledge_card import KnowledgeCard
from athena.schemas.outline import DEFAULT_TODO_MARKER, Outline, OutlineSection


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
    critiques = [Critique(claim="gap", type="gap", evidence_paper_ids=["a:1"], confidence=0.8)]
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
        sources_ok={"arxiv": True, "semantic_scholar": True, "crossref": True},
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
        sources_ok={"arxiv": True, "semantic_scholar": False, "crossref": True},
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
        ValidationResult(
            status="verified", citation=build_citations_for_validation([_card("a:1")], [], None)[0]
        )
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


def test_controller_finishes_when_verified():
    from athena.graph.nodes import diagnose_repair, route_after_controller
    from athena.schemas.citation import Citation, ValidationResult

    cit = Citation(title="T", doi="10.1/x")
    state = {
        "validation_report": [ValidationResult(status="verified", citation=cit)],
        "papers": [_card("a:1")] * 10,
        "revisions": 0,
    }
    action, _ = diagnose_repair(state)
    assert action == "finish"
    assert route_after_controller({"repair_action": action}) == "finish"


def test_controller_broadens_when_unverified():
    from athena.graph.nodes import diagnose_repair, route_after_controller
    from athena.schemas.citation import Citation, ValidationResult

    cit = Citation(title="T", doi="10.1/x")
    state = {
        "validation_report": [
            ValidationResult(status="not_found", citation=cit),
            ValidationResult(status="mismatch", citation=cit),
        ],
        "papers": [_card("a:1")] * 10,
        "revisions": 0,
        "constraints": {"max_revisions": 1, "revision_fake_threshold": 0.3, "min_cards": 1},
    }
    action, _ = diagnose_repair(state)
    assert action == "research_broaden"
    assert route_after_controller({"repair_action": action}) == "research"


def test_controller_relaxes_when_too_few_papers():
    from athena.graph.nodes import diagnose_repair, route_after_controller

    state = {
        "validation_report": [],
        "papers": [_card("a:1")],
        "revisions": 0,
        "constraints": {"max_revisions": 1, "min_cards": 10},
    }
    action, _ = diagnose_repair(state)
    assert action == "research_relax"
    assert route_after_controller({"repair_action": action}) == "research"


def test_controller_recritiques_when_low_grounding():
    from athena.graph.nodes import diagnose_repair, route_after_controller
    from athena.schemas.citation import Citation, ValidationResult

    cit = Citation(title="T", doi="10.1/x")
    state = {
        "validation_report": [ValidationResult(status="verified", citation=cit)],
        "papers": [_card("a:1")] * 10,
        "critic_meta": {"evidence_grounding_rate": 0.2},
        "revisions": 0,
        "constraints": {"max_revisions": 1, "min_cards": 1, "revision_grounding_threshold": 0.5},
    }
    action, _ = diagnose_repair(state)
    assert action == "recritique"
    assert route_after_controller({"repair_action": action}) == "critic"


def test_controller_respects_budget():
    from athena.graph.nodes import diagnose_repair

    state = {
        "validation_report": [],
        "papers": [_card("a:1")],
        "revisions": 1,
        "constraints": {"max_revisions": 1, "min_cards": 10},
    }
    action, _ = diagnose_repair(state)
    assert action == "finish"


@patch("athena.graph.nodes.run_planner")
@patch("athena.graph.nodes.run_research")
@patch("athena.graph.nodes.run_critic")
@patch("athena.graph.nodes.run_writer")
@patch("athena.graph.nodes.validate_citations")
def test_pipeline_revision_loop_runs_once(
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
        topic="rag", plan=default_task_plan("rag"), model="m", used_fallback=True, errors=[]
    )
    mock_research.return_value = ResearchResult(
        topic="rag",
        cards=[_card("a:1")],
        errors=[],
        sources_ok={"arxiv": True, "semantic_scholar": True, "crossref": True},
    )
    mock_critic.return_value = CriticResult(
        topic="rag",
        corpus_size=1,
        critiques=[Critique(claim="c", type="gap", evidence_paper_ids=["a:1"], confidence=0.8)],
        dropped_unsupported=0,
        evidence_grounding_rate=1.0,
        model="m",
        errors=[],
    )
    mock_writer.return_value = WriterResult(
        topic="rag",
        outline=Outline(
            title="O",
            sections=[
                OutlineSection(
                    heading="I", bullets=[DEFAULT_TODO_MARKER], evidence_paper_ids=["a:1"]
                )
            ],
        ),
        model="m",
        used_fallback=False,
        errors=[],
    )
    citation = build_citations_for_validation([_card("a:1")], [], None)[0]
    # First validation pass: unresolved → triggers one revision; second pass also unresolved.
    mock_validate.return_value = [ValidationResult(status="not_found", citation=citation)]

    graph = build_athena_graph(checkpointer=MemorySaver(), use_sqlite=False)
    final = graph.invoke(
        initial_state(
            "rag", constraints={"min_cards": 1, "per_source_limit": 5, "max_revisions": 1}
        ),
        config={"configurable": {"thread_id": "test-revision-1"}},
    )
    report = state_to_report(final)
    # Loop ran exactly once (budget=1): validator executed twice, revisions==1.
    assert report["revisions"] == 1
    assert mock_validate.call_count == 2
    assert any(t["step"] == "controller" for t in report["trace"])


def test_prepare_citations_node():
    papers = [_card("a:1")]
    critiques = [Critique(claim="g", type="gap", evidence_paper_ids=["a:1"], confidence=0.7)]
    out = prepare_citations_node(
        {
            "papers": papers,
            "critiques": critiques,
            "draft": Outline(title="T", sections=[]),
            "trace": [],
        }
    )
    assert len(out["citations"]) == 1
