"""Load published HALLMARK baseline scores for side-by-side comparison."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_BASELINES = ("doi_only", "bibtexupdater")


def _baseline_path(data_dir: Path, name: str, split: str) -> Path:
    return data_dir / "v1.0" / "baseline_results" / f"{name}_{split}.json"


def load_baseline_result(data_dir: Path, name: str, split: str) -> dict[str, Any] | None:
    path = _baseline_path(data_dir, name, split)
    if not path.is_file():
        return None
    with open(path) as f:
        return json.load(f)


def format_metrics_row(tool: str, metrics: dict[str, Any]) -> str:
    dr = metrics.get("detection_rate")
    f1 = metrics.get("f1_hallucination")
    tw = metrics.get("tier_weighted_f1")
    fpr = metrics.get("false_positive_rate")
    ece = metrics.get("ece")
    n = metrics.get("num_entries", "—")
    return (
        f"| {tool} | {n} | "
        f"{dr:.3f} | {f1:.3f} | {tw:.3f} | {fpr:.3f} | {ece:.3f} |"
        if all(isinstance(x, (int, float)) for x in (dr, f1, tw, fpr, ece))
        else f"| {tool} | {n} | — | — | — | — | — |"
    )


def comparison_markdown(
    athena_metrics: dict[str, Any],
    data_dir: Path,
    split: str,
    *,
    baselines: tuple[str, ...] = DEFAULT_BASELINES,
    tool_name: str = "athena-validator",
) -> str:
    """Build a markdown table: Athena vs bundled HALLMARK baselines."""
    lines = [
        f"# HALLMARK comparison ({split})",
        "",
        "| Tool | N | Detection rate | F1-H | Tier-weighted F1 | FPR | ECE |",
        "|------|---:|---:|---:|---:|---:|---:|",
        format_metrics_row(tool_name, athena_metrics),
    ]
    for name in baselines:
        row = load_baseline_result(data_dir, name, split)
        if row:
            lines.append(format_metrics_row(name, row))
    return "\n".join(lines) + "\n"
