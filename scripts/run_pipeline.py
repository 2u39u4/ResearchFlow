#!/usr/bin/env python3
"""CLI: run full Athena pipeline (Planner → Research → Critic → Writer → Validator)."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from athena.graph.build_graph import build_athena_graph, initial_state
from athena.graph.report import state_to_report
from athena.agents.research import CriticalResearchSourcesError
from athena.storage.sqlite import init_db, persist_traces


def main() -> int:
    parser = argparse.ArgumentParser(description="Athena end-to-end pipeline")
    parser.add_argument("topic", help="Research topic")
    parser.add_argument("--thread-id", help="LangGraph thread id for checkpoint resume")
    parser.add_argument(
        "--min-cards",
        type=int,
        default=10,
        help="Minimum retrieved papers (default: 10)",
    )
    parser.add_argument(
        "--per-source",
        type=int,
        default=15,
        help="Max papers per retrieval source",
    )
    parser.add_argument(
        "--no-checkpoint",
        action="store_true",
        help="Use in-memory checkpointer only",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSON report to file",
    )
    args = parser.parse_args()

    init_db()
    graph = build_athena_graph(use_sqlite=not args.no_checkpoint)
    thread_id = args.thread_id or f"athena-{uuid.uuid4().hex[:12]}"
    config = {"configurable": {"thread_id": thread_id}}

    state = initial_state(
        args.topic,
        constraints={"min_cards": args.min_cards, "per_source_limit": args.per_source},
        run_id=thread_id,
    )

    print(f"Running pipeline (thread_id={thread_id})...", file=sys.stderr)
    try:
        final = graph.invoke(state, config=config)
    except CriticalResearchSourcesError as exc:
        for err in exc.errors:
            print(f"Research failed: {err}", file=sys.stderr)
        return 1
    report = state_to_report(final)

    if report.get("run_id"):
        n = persist_traces(str(report["run_id"]), report.get("trace") or [])
        print(f"Persisted {n} trace rows to SQLite.", file=sys.stderr)

    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
        print(f"Wrote {args.output}", file=sys.stderr)
    else:
        print(text)

    papers = report.get("papers") or []
    if len(papers) < args.min_cards:
        print(
            f"Warning: only {len(papers)} papers retrieved (min={args.min_cards})",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
