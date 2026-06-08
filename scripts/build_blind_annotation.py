#!/usr/bin/env python3
"""Build a blind A/B depth/preference annotation packet from RQ1 results."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.judges.blind_anchor import build_blind_packet


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a blind human-annotation packet")
    parser.add_argument("--rq1", type=Path, default=Path("results/experiments/rq1/latest.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("eval/judges/blind"))
    parser.add_argument("--fraction", type=float, default=0.2)
    parser.add_argument("--repeat", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.rq1.exists():
        print(f"RQ1 results not found: {args.rq1}", file=sys.stderr)
        print("Run `python scripts/run_experiments.py rq1` first.", file=sys.stderr)
        return 1

    paths = build_blind_packet(
        args.rq1,
        args.out_dir,
        fraction=args.fraction,
        repeat=args.repeat,
        seed=args.seed,
    )
    print("Blind packet written:")
    for name, p in paths.items():
        print(f"  {name}: {p}")
    print("\nNext: read", paths["packet"], "and fill", paths["rating_csv"])
    print("Then: python scripts/ingest_human_anchor.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
