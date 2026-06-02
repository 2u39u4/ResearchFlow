#!/usr/bin/env python3
"""CLI: validate a JSON list of citations (deterministic, no LLM)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from athena.graph.nodes import validate_citations_node
from athena.schemas.citation import Citation
from athena.tools.citation_validator import validate_citations

SAMPLE = [
    {
        "title": "Attention Is All You Need",
        "authors": ["Ashish Vaswani", "Noam Shazeer"],
        "year": 2017,
        "doi": "10.48550/arxiv.1706.03762",
    },
    {
        "title": "This Paper Does Not Exist 12345",
        "authors": ["Fake Author"],
        "year": 2099,
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Athena W3 citation validator")
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to JSON file (list of citation objects). Omit to use built-in sample.",
    )
    parser.add_argument(
        "--use-graph-node",
        action="store_true",
        help="Run via validate_citations_node (same as future LangGraph step)",
    )
    args = parser.parse_args()

    if args.input:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        data = SAMPLE
        print("Using built-in sample (1 real + 1 fake).\n", file=sys.stderr)

    citations = [Citation.model_validate(item) for item in data]

    if args.use_graph_node:
        out = validate_citations_node({"citations": [c.model_dump() for c in citations]})
        payload = out["validation_report_json"]
    else:
        results = validate_citations(citations)
        payload = [r.model_dump() for r in results]

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    fake_rate = sum(1 for r in payload if r["status"] == "not_found") / max(len(payload), 1)
    print(f"\nnot_found rate: {fake_rate:.0%}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
