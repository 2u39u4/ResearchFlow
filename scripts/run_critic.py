#!/usr/bin/env python3
"""CLI: Research retrieval + Critic Agent (evidence-grounded critiques)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from athena.agents.critic import run_critic, supported_only
from athena.agents.research import run_research
from athena.schemas.knowledge_card import KnowledgeCard


def _load_cards(path: Path) -> list[KnowledgeCard]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "cards" in data:
        raw = data["cards"]
    elif isinstance(data, list):
        raw = data
    else:
        raise ValueError("JSON must be a list of cards or {cards: [...]}")
    return [KnowledgeCard.model_validate(item) for item in raw]


def main() -> int:
    parser = argparse.ArgumentParser(description="Athena W5 critic (gap / weakness / relative novelty)")
    parser.add_argument("topic", help="Research topic")
    parser.add_argument(
        "--papers-json",
        type=Path,
        help="Skip retrieval; load KnowledgeCards from JSON file",
    )
    parser.add_argument("--per-source", type=int, default=15, help="Research: max per source")
    parser.add_argument("--min-cards", type=int, default=10, help="Research: minimum unique cards")
    parser.add_argument(
        "--supported-only",
        action="store_true",
        help="Print only supported critiques in summary line",
    )
    args = parser.parse_args()

    if args.papers_json:
        cards = _load_cards(args.papers_json)
        topic = args.topic
    else:
        research = run_research(
            args.topic,
            per_source_limit=args.per_source,
            min_cards=args.min_cards,
        )
        cards = research.cards
        topic = research.topic
        if research.errors:
            print("Research warnings:", file=sys.stderr)
            for err in research.errors:
                print(f"  - {err}", file=sys.stderr)
        if len(cards) < args.min_cards:
            print(
                f"Need at least {args.min_cards} papers for critic; got {len(cards)}",
                file=sys.stderr,
            )
            return 1

    result = run_critic(topic, cards)
    print(result.to_json())

    supported = supported_only(result.critiques)
    print(
        f"\nSummary: {len(supported)} supported / {len(result.critiques)} total "
        f"(grounding rate {result.evidence_grounding_rate:.2f}, model={result.model})",
        file=sys.stderr,
    )
    if args.supported_only:
        for c in supported:
            print(f"  [{c.type}] {c.claim[:100]}...", file=sys.stderr)

    return 0 if supported else 1


if __name__ == "__main__":
    raise SystemExit(main())
