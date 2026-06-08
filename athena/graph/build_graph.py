"""Assemble the Athena LangGraph pipeline."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from athena.config import get_settings
from athena.graph.nodes import (
    critic_node,
    planner_node,
    prepare_citations_node,
    research_node,
    revise_node,
    route_after_validation,
    validate_citations_node,
    writer_node,
)
from athena.graph.state import AthenaState


def get_sqlite_checkpointer(db_path: Path | None = None) -> Any:
    """LangGraph SQLite checkpointer for resume-after-interrupt."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    settings = get_settings()
    settings.ensure_dirs()
    path = db_path or settings.athena_checkpoint_db
    conn = sqlite3.connect(str(path), check_same_thread=False)
    return SqliteSaver(conn)


def build_athena_graph(*, checkpointer: Any | None = None, use_sqlite: bool = True):
    """
    Planner → Research → Critic → Writer → prepare_citations → Validator
                  ▲                                                │
                  └──────────── revise (if too many unverified) ◄──┘

    The Validator emits a conditional edge: when the unverified-citation ratio
    exceeds ``revision_fake_threshold`` and the ``max_revisions`` budget remains,
    the graph loops back through Research with broader retrieval; otherwise it ends.
    """
    graph = StateGraph(AthenaState)
    graph.add_node("planner", planner_node)
    graph.add_node("research", research_node)
    graph.add_node("critic", critic_node)
    graph.add_node("writer", writer_node)
    graph.add_node("prepare_citations", prepare_citations_node)
    graph.add_node("validator", validate_citations_node)
    graph.add_node("revise", revise_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "research")
    graph.add_edge("research", "critic")
    graph.add_edge("critic", "writer")
    graph.add_edge("writer", "prepare_citations")
    graph.add_edge("prepare_citations", "validator")
    graph.add_conditional_edges(
        "validator",
        route_after_validation,
        {"revise": "revise", "finish": END},
    )
    graph.add_edge("revise", "research")

    if checkpointer is None and use_sqlite:
        try:
            checkpointer = get_sqlite_checkpointer()
        except Exception:
            checkpointer = MemorySaver()
    elif checkpointer is None:
        checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)


def initial_state(
    topic: str,
    *,
    constraints: dict | None = None,
    run_id: str | None = None,
) -> AthenaState:
    return AthenaState(
        topic=topic.strip(),
        constraints=constraints or {},
        run_id=run_id,
        revisions=0,
        revision_log=[],
        trace=[],
    )
