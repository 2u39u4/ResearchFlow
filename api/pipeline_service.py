"""Background pipeline execution with SSE event buffers."""

from __future__ import annotations

import logging
import threading
import uuid
from collections import defaultdict
from typing import Any

from api.database import update_run
from athena.agents.research import CriticalResearchSourcesError
from athena.graph.build_graph import build_athena_graph, initial_state
from athena.graph.report import state_to_report
from athena.storage.sqlite import init_db, persist_traces

logger = logging.getLogger(__name__)

PIPELINE_STEPS = [
    "planner",
    "research",
    "critic",
    "writer",
    "prepare_citations",
    "validator",
    "controller",
]

_run_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
_run_lock = threading.Lock()


def _append_event(run_id: str, step: str, status: str, detail: str = "") -> None:
    with _run_lock:
        _run_events[run_id].append({"step": step, "status": status, "detail": detail})


def get_events(run_id: str, after: int = 0) -> list[dict[str, Any]]:
    with _run_lock:
        return list(_run_events[run_id][after:])


def event_count(run_id: str) -> int:
    with _run_lock:
        return len(_run_events[run_id])


def clear_events(run_id: str) -> None:
    with _run_lock:
        _run_events.pop(run_id, None)


def run_pipeline_async(
    run_id: str,
    user_id: str,
    topic: str,
    constraints: dict[str, Any],
) -> None:
    """Start pipeline in a background thread."""

    def _worker() -> None:
        try:
            update_run(run_id, status="running")
            _append_event(run_id, "pipeline", "started", topic)
            init_db()
            graph = build_athena_graph(use_sqlite=True)
            thread_id = f"api-{user_id}-{uuid.uuid4().hex[:8]}"
            config = {"configurable": {"thread_id": thread_id}}
            state = initial_state(topic, constraints=constraints, run_id=run_id)

            for event in graph.stream(state, config=config, stream_mode="updates"):
                for node_name in event:
                    _append_event(run_id, node_name, "completed")
                    logger.info("Run %s completed node %s", run_id, node_name)

            snapshot = graph.get_state(config)
            final_state = dict(snapshot.values) if snapshot and snapshot.values else {}
            report = state_to_report(final_state)
            if report.get("run_id"):
                persist_traces(str(report["run_id"]), report.get("trace") or [])
            update_run(run_id, status="completed", report=report)
            _append_event(run_id, "pipeline", "completed")
        except CriticalResearchSourcesError as exc:
            msg = "; ".join(exc.errors) if exc.errors else str(exc)
            update_run(run_id, status="failed", error_message=msg)
            _append_event(run_id, "pipeline", "failed", msg)
        except Exception as exc:
            logger.exception("Pipeline failed for run %s", run_id)
            update_run(run_id, status="failed", error_message=str(exc))
            _append_event(run_id, "pipeline", "failed", str(exc))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
