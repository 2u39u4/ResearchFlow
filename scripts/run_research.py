#!/usr/bin/env python3
"""CLI: run Research Agent for a topic and print KnowledgeCards as JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from athena.agents.research import run_research


def main() -> int:
    parser = argparse.ArgumentParser(description="Athena research retrieval")
    parser.add_argument("topic", help="Research topic or query string")
    parser.add_argument(
        "--per-source",
        type=int,
        default=15,
        help="Max papers per source before dedup (default: 15)",
    )
    parser.add_argument(
        "--min-cards",
        type=int,
        default=10,
        help="Warn if fewer unique cards than this (default: 10)",
    )
    args = parser.parse_args()

    result = run_research(
        args.topic,
        per_source_limit=args.per_source,
        min_cards=args.min_cards,
    )

    print(result.to_json())
    if result.errors:
        print("\nWarnings:", file=sys.stderr)
        for err in result.errors:
            print(f"  - {err}", file=sys.stderr)

    if not result.critical_sources_ok:
        return 1

    if len(result.cards) < args.min_cards:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
