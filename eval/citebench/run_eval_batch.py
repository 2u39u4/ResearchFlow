"""Resumable HALLMARK evaluation in fixed-size batches with per-entry checkpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from eval.citebench.baseline_table import comparison_markdown
from eval.citebench.checkpoint import (
    BatchCheckpointState,
    append_prediction_jsonl,
    batch_result_path,
    checkpoint_paths,
    load_predictions_jsonl,
    load_state,
    reset_checkpoint,
    save_state,
)
from eval.citebench.hallmark_adapter import run_athena_on_blind_entries
from eval.citebench.run_eval import _default_hallmark_root, _ensure_hallmark_import, analyze_misclassifications


def _print_metrics(result: Any, *, prefix: str = "") -> None:
    print(f"{prefix}Results: {result.tool_name} on {result.split_name} (N={result.num_entries})")
    print(f"{prefix}  Detection rate:    {result.detection_rate:.3f}")
    fpr = result.false_positive_rate
    print(
        f"{prefix}  False pos. rate:   {fpr:.3f}"
        if fpr is not None
        else f"{prefix}  False pos. rate:   n/a"
    )
    print(f"{prefix}  F1 (halluc.):      {result.f1_hallucination:.3f}")
    print(f"{prefix}  Tier-weighted F1:  {result.tier_weighted_f1:.3f}")
    print(f"{prefix}  ECE:               {result.ece:.3f}")
    print(f"{prefix}  MCC:               {result.mcc:.3f}")


def _predictions_for_entries(entries: list[Any], pred_by_key: dict[str, Any]) -> list[Any]:
    from hallmark.dataset.schema import Prediction

    missing = [e.bibtex_key for e in entries if e.bibtex_key not in pred_by_key]
    if missing:
        raise RuntimeError(f"Missing predictions for {len(missing)} entries (first: {missing[0]!r})")
    return [Prediction.from_dict(pred_by_key[e.bibtex_key]) for e in entries]


def _first_pending_index(entries: list[Any], pred_by_key: dict[str, Any]) -> int:
    for i, entry in enumerate(entries):
        if entry.bibtex_key not in pred_by_key:
            return i
    return len(entries)


def run_batch_eval(
    entries: list[Any],
    *,
    split: str,
    tool_name: str,
    delay_seconds: float,
    batch_size: int,
    checkpoint_dir: Path,
    data_dir: Path,
    output: Path | None = None,
    comparison_md: Path | None = None,
    analyze: bool = False,
    reset: bool = False,
    max_batches: int = 0,
) -> int:
    from hallmark.dataset.schema import Prediction
    from hallmark.evaluation.metrics import evaluate

    paths = checkpoint_paths(checkpoint_dir)
    if reset:
        reset_checkpoint(checkpoint_dir)
        paths = checkpoint_paths(checkpoint_dir)

    pred_dicts = load_predictions_jsonl(paths["predictions"])
    state = load_state(paths["state"])
    if state is None:
        state = BatchCheckpointState.fresh(
            split=split,
            tool_name=tool_name,
            delay_seconds=delay_seconds,
            batch_size=batch_size,
            total_entries=len(entries),
        )
        save_state(paths["state"], state)
    elif state.total_entries != len(entries):
        print(
            f"Warning: checkpoint total_entries={state.total_entries} "
            f"!= current split size {len(entries)}",
            file=sys.stderr,
        )

    start = _first_pending_index(entries, pred_dicts)
    if start >= len(entries):
        print(f"Checkpoint complete: {len(pred_dicts)}/{len(entries)} predictions on disk.")
    else:
        print(
            f"Resuming from entry {start + 1}/{len(entries)} "
            f"({len(pred_dicts)} predictions loaded, batch_size={batch_size}, delay={delay_seconds}s)"
        )

    batch_index = state.last_batch_index + 1
    batches_run = 0
    while start < len(entries):
        end = min(start + batch_size, len(entries))
        batch_entries = entries[start:end]
        batch_num = batch_index + 1
        print(
            f"\n[batch {batch_num}] entries {start + 1}-{end} / {len(entries)} …",
            flush=True,
        )

        def _on_prediction(local_i: int, blind_entry: Any, pred: Prediction) -> None:
            global_i = start + local_i
            pred_dicts[pred.bibtex_key] = pred.to_dict()
            append_prediction_jsonl(paths["predictions"], pred_dicts[pred.bibtex_key])
            state.completed_count = len(pred_dicts)
            save_state(paths["state"], state)
            if (global_i + 1) % 10 == 0 or global_i + 1 == end:
                print(f"  … checkpoint {global_i + 1}/{len(entries)}", flush=True)

        blind = [e.to_blind() for e in batch_entries]
        batch_predictions = run_athena_on_blind_entries(
            blind,
            delay_seconds=delay_seconds,
            on_prediction=_on_prediction,
        )

        batch_result = evaluate(
            entries=batch_entries,
            predictions=batch_predictions,
            tool_name=tool_name,
            split_name=split,
        )
        batch_metrics = json.loads(batch_result.to_json())
        batch_path = batch_result_path(paths["batches"], batch_index, end)
        batch_path.write_text(batch_result.to_json())
        print(f"Wrote batch metrics {batch_path}")
        _print_metrics(batch_result, prefix="  ")

        state.completed_count = len(pred_dicts)
        state.last_batch_index = batch_index
        save_state(paths["state"], state)

        batch_index += 1
        batches_run += 1
        start = end
        if max_batches > 0 and batches_run >= max_batches:
            print(f"\nStopped after {batches_run} batch(es) (--max-batches={max_batches}).")
            break

    completed_entries: list[Any] = []
    for entry in entries:
        if entry.bibtex_key in pred_dicts:
            completed_entries.append(entry)
        else:
            break

    if not completed_entries:
        print("No predictions completed yet.", file=sys.stderr)
        return 1

    all_predictions = _predictions_for_entries(completed_entries, pred_dicts)
    merged = evaluate(
        entries=completed_entries,
        predictions=all_predictions,
        tool_name=tool_name,
        split_name=split,
    )
    merged_dict = json.loads(merged.to_json())
    paths["merged_metrics"].write_text(merged.to_json())
    partial = len(completed_entries) < len(entries)
    print(
        f"\n{'Partial' if partial else 'Merged'} metrics "
        f"({len(completed_entries)}/{len(entries)}) written to {paths['merged_metrics']}"
    )
    _print_metrics(merged)

    if output and not partial:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(merged.to_json())
        print(f"Wrote {output}")

    if comparison_md and not partial:
        md = comparison_markdown(merged_dict, data_dir, split, tool_name=tool_name)
        comparison_md.parent.mkdir(parents=True, exist_ok=True)
        comparison_md.write_text(md)
        print(f"Wrote {comparison_md}")

    if analyze and not partial:
        analyze_misclassifications(entries, all_predictions)
    elif analyze and partial:
        analyze_misclassifications(completed_entries, all_predictions)

    return 0


def main(argv: list[str] | None = None) -> int:
    _ensure_hallmark_import()
    from hallmark.dataset.loader import load_split

    parser = argparse.ArgumentParser(
        description="Resumable HALLMARK eval: batch metrics + per-entry checkpoint"
    )
    parser.add_argument("--split", default="dev_public", help="HALLMARK split name")
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=Path("results/hallmark_checkpoints/dev_public"),
        help="Directory for state.json, predictions.jsonl, batches/",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Entries per batch (default: 50)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Seconds between entries (default: 0.2)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="HALLMARK data/ directory (default: $HALLMARK_ROOT/data)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/athena_dev_public_full.json"),
        help="Final merged EvaluationResult JSON",
    )
    parser.add_argument(
        "--comparison-md",
        type=Path,
        default=Path("results/athena_vs_baselines_full.md"),
        help="Markdown comparison vs baselines",
    )
    parser.add_argument("--analyze", action="store_true", help="Print misclassification samples")
    parser.add_argument("--reset", action="store_true", help="Clear checkpoint and start over")
    parser.add_argument(
        "--max-batches",
        type=int,
        default=0,
        help="Stop after N batches this run (0 = run until complete)",
    )
    parser.add_argument("--tool-name", default="athena-validator")
    args = parser.parse_args(argv)

    hallmark_root = _default_hallmark_root()
    data_dir = args.data_dir or (hallmark_root / "data")
    if not data_dir.is_dir():
        print(f"HALLMARK data not found: {data_dir}", file=sys.stderr)
        return 1

    entries = load_split(args.split, data_dir=data_dir)
    print(
        f"HALLMARK batch eval split={args.split!r} entries={len(entries)} "
        f"checkpoint_dir={args.checkpoint_dir}"
    )

    return run_batch_eval(
        entries,
        split=args.split,
        tool_name=args.tool_name,
        delay_seconds=args.delay,
        batch_size=args.batch_size,
        checkpoint_dir=args.checkpoint_dir,
        data_dir=data_dir,
        output=args.output,
        comparison_md=args.comparison_md,
        analyze=args.analyze,
        reset=args.reset,
        max_batches=args.max_batches,
    )


if __name__ == "__main__":
    raise SystemExit(main())
