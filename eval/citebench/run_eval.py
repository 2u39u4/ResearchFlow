"""Run Athena CitationValidator on HALLMARK and print official metrics."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

from eval.citebench.baseline_table import comparison_markdown
from eval.citebench.hallmark_adapter import run_athena_on_blind_entries


def _default_hallmark_root() -> Path:
    env = os.environ.get("HALLMARK_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / ".vendor" / "hallmark"


def _ensure_hallmark_import() -> None:
    try:
        import hallmark  # noqa: F401
    except ImportError as exc:
        print(
            "HALLMARK is not on PYTHONPATH.\n"
            "  bash scripts/install_hallmark.sh\n"
            "  export HALLMARK_ROOT=/path/to/hallmark-repo\n"
            "  python3.11 scripts/run_hallmark_eval.py ...",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def print_split_stats(entries: list) -> None:
    from hallmark.dataset.schema import HALLUCINATION_TIER_MAP, HallucinationType

    labels = Counter(e.label for e in entries)
    tiers = Counter(e.difficulty_tier for e in entries if e.label == "HALLUCINATED")
    types = Counter(e.hallucination_type for e in entries if e.hallucination_type)
    print(f"  Total entries: {len(entries)}")
    print(f"  Labels: {dict(labels)}")
    print("  Hallucination tiers:")
    for tier in (1, 2, 3):
        print(f"    Tier {tier}: {tiers.get(tier, 0)}")
    print("  Top hallucination types:")
    for htype, count in types.most_common(8):
        tier = HALLUCINATION_TIER_MAP.get(HallucinationType(htype), "?") if htype else "?"
        print(f"    {htype} (tier {tier}): {count}")


def analyze_misclassifications(entries: list, predictions: list, *, limit: int = 5) -> None:
    pred_map = {p.bibtex_key: p for p in predictions}
    false_pos = [
        e for e in entries if e.label == "VALID" and pred_map[e.bibtex_key].label == "HALLUCINATED"
    ]
    false_neg = [
        e for e in entries if e.label == "HALLUCINATED" and pred_map[e.bibtex_key].label == "VALID"
    ]
    print("\n  Misclassification summary:")
    print(f"    False positives (valid flagged): {len(false_pos)}")
    print(f"    False negatives (hallucination missed): {len(false_neg)}")

    if false_pos:
        print(f"\n  Sample false positives (up to {limit}):")
        for e in false_pos[:limit]:
            p = pred_map[e.bibtex_key]
            title = (e.fields.get("title") or "")[:60]
            print(f"    {e.bibtex_key}: {title!r} — {p.reason[:80]}")

    if false_neg:
        print(f"\n  Sample false negatives (up to {limit}):")
        for e in false_neg[:limit]:
            p = pred_map[e.bibtex_key]
            tier = e.difficulty_tier or "?"
            htype = e.hallucination_type or "?"
            title = (e.fields.get("title") or "")[:60]
            print(f"    [{htype} T{tier}] {e.bibtex_key}: {title!r} — {p.reason[:80]}")


def main(argv: list[str] | None = None) -> int:
    _ensure_hallmark_import()
    from hallmark.dataset.loader import load_split
    from hallmark.evaluation.metrics import evaluate

    parser = argparse.ArgumentParser(description="Evaluate Athena validator on HALLMARK")
    parser.add_argument("--split", default="dev_public", help="HALLMARK split name")
    parser.add_argument("--limit", type=int, default=0, help="Max entries (0 = all)")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="HALLMARK data/ directory (default: $HALLMARK_ROOT/data)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between API calls (0 = no delay)",
    )
    parser.add_argument("--stats-only", action="store_true", help="Print split stats and exit")
    parser.add_argument("--output", type=Path, help="Write EvaluationResult JSON")
    parser.add_argument(
        "--comparison-md",
        type=Path,
        help="Write markdown comparison vs doi_only / bibtexupdater",
    )
    parser.add_argument("--analyze", action="store_true", help="Print misclassification samples")
    parser.add_argument("--tool-name", default="athena-validator")
    args = parser.parse_args(argv)

    hallmark_root = _default_hallmark_root()
    data_dir = args.data_dir or (hallmark_root / "data")
    if not data_dir.is_dir():
        print(f"HALLMARK data not found: {data_dir}", file=sys.stderr)
        return 1

    entries = load_split(args.split, data_dir=data_dir)
    if args.limit > 0:
        entries = entries[: args.limit]

    print(f"HALLMARK split={args.split!r} entries={len(entries)} data_dir={data_dir}")

    if args.stats_only:
        print_split_stats(entries)
        return 0

    blind = [e.to_blind() for e in entries]
    print(f"Running Athena validator (delay={args.delay}s per entry)...")
    predictions = run_athena_on_blind_entries(blind, delay_seconds=args.delay)

    result = evaluate(
        entries=entries,
        predictions=predictions,
        tool_name=args.tool_name,
        split_name=args.split,
    )

    print(f"\nResults: {result.tool_name} on {result.split_name}")
    print(f"  Detection rate:    {result.detection_rate:.3f}")
    fpr = result.false_positive_rate
    print(f"  False pos. rate:   {fpr:.3f}" if fpr is not None else "  False pos. rate:   n/a")
    print(f"  F1 (halluc.):      {result.f1_hallucination:.3f}")
    print(f"  Tier-weighted F1:  {result.tier_weighted_f1:.3f}")
    print(f"  ECE:               {result.ece:.3f}")
    print(f"  MCC:               {result.mcc:.3f}")
    if result.per_tier_metrics:
        print("  Per-tier (hallucinated entries):")
        for tier in (1, 2, 3):
            m = result.per_tier_metrics.get(tier)
            if m:
                print(
                    f"    Tier {tier}: DR={m['detection_rate']:.3f} "
                    f"F1={m['f1']:.3f} n={m.get('num_hallucinated', m.get('count', '?'))}"
                )

    metrics_dict = json.loads(result.to_json())

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.to_json())
        print(f"\nWrote {args.output}")

    if args.comparison_md:
        md = comparison_markdown(metrics_dict, data_dir, args.split, tool_name=args.tool_name)
        args.comparison_md.parent.mkdir(parents=True, exist_ok=True)
        args.comparison_md.write_text(md)
        print(f"Wrote {args.comparison_md}")

    if args.analyze:
        analyze_misclassifications(entries, predictions)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
