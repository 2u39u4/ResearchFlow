#!/usr/bin/env python3
"""Generate human anchor CSV and print agreement vs LLM judge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.judges.human_anchor import compute_agreement, write_human_anchor_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Build human anchor CSV from RQ1 results")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("eval/judges/human_anchor_template.csv"),
    )
    parser.add_argument(
        "--rq1",
        type=Path,
        default=Path("results/experiments/rq1/latest.json"),
    )
    parser.add_argument("--fraction", type=float, default=0.2)
    parser.add_argument("--repeat", type=int, default=0)
    parser.add_argument("--json", action="store_true", help="Print agreement stats as JSON")
    args = parser.parse_args()

    out = write_human_anchor_csv(
        args.csv,
        rq1_path=args.rq1,
        fraction=args.fraction,
        repeat=args.repeat,
    )
    stats = compute_agreement(out, rq1_path=args.rq1)
    if args.json:
        print(json.dumps({"csv": str(out), **stats}, indent=2))
    else:
        print(f"Wrote {out} ({stats['n_human_rows']} rows)")
        if stats.get("depth_multi_kappa") is not None:
            print(
                f"Agreement: multi κ={stats['depth_multi_kappa']}, "
                f"single κ={stats['depth_single_kappa']}, "
                f"multi ρ={stats['depth_multi_spearman']}, "
                f"preference={stats['preference_agreement_rate']}"
            )
        else:
            print(
                f"Agreement: depth_a κ={stats.get('depth_a_kappa')}, "
                f"depth_b κ={stats.get('depth_b_kappa')}, "
                f"depth_a ρ={stats.get('depth_a_spearman')}, "
                f"preference={stats['preference_agreement_rate']}"
            )


if __name__ == "__main__":
    main()
