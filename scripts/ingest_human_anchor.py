#!/usr/bin/env python3
"""Un-blind a filled rating sheet into the standard human-anchor CSV and report agreement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.judges.blind_anchor import ingest_blind_ratings
from eval.judges.human_anchor import compute_agreement


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest filled blind ratings -> human anchor")
    parser.add_argument("--blind-dir", type=Path, default=Path("eval/judges/blind"))
    parser.add_argument("--rating-csv", type=Path, default=None)
    parser.add_argument("--keymap", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("eval/judges/human_anchor_human.csv"))
    parser.add_argument("--rq1", type=Path, default=Path("results/experiments/rq1/latest.json"))
    parser.add_argument("--json", action="store_true", help="Print agreement stats as JSON")
    args = parser.parse_args()

    rating_csv = args.rating_csv or (args.blind_dir / "rating_sheet.csv")
    keymap = args.keymap or (args.blind_dir / "_keymap.json")
    for p in (rating_csv, keymap):
        if not p.exists():
            print(f"Missing: {p}. Run scripts/build_blind_annotation.py first.", file=sys.stderr)
            return 1

    out = ingest_blind_ratings(rating_csv, keymap, args.out)
    print(f"Wrote real human anchor: {out}")

    if args.rq1.exists():
        stats = compute_agreement(out, rq1_path=args.rq1)
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print(f"Rows: {stats.get('n_human_rows')} (matched {stats.get('n_matched')})")
            if stats.get("depth_multi_kappa") is not None:
                print(
                    f"Agreement vs LLM judge — depth multi κ={stats['depth_multi_kappa']}, "
                    f"single κ={stats['depth_single_kappa']}, "
                    f"multi ρ={stats['depth_multi_spearman']}, "
                    f"preference={stats['preference_agreement_rate']}"
                )
    else:
        print(f"(RQ1 results {args.rq1} not found — skipped agreement computation)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
