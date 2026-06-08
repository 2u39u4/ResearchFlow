"""Generate paper-ready figures from experiment JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from eval.analysis.stats import mean_std


def _load_latest(rq: str) -> dict[str, Any] | None:
    path = Path("results/experiments") / rq / "latest.json"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def plot_rq1(out_dir: Path) -> Path | None:
    data = _load_latest("rq1")
    if not data:
        return None
    rows = data.get("rows") or []
    cov_m = [r["coverage"]["multi_agent"] for r in rows]
    cov_s = [r["coverage"]["single_agent"] for r in rows]
    mm = mean_std(cov_m)
    ms = mean_std(cov_s)

    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["Multi-Agent", "Single-Agent"]
    means = [mm["mean"], ms["mean"]]
    stds = [mm["std"], ms["std"]]
    ax.bar(labels, means, yerr=stds, capsize=6, color=["#2a6f97", "#a8dadc"])
    ax.set_ylabel("Coverage (mean ± std)")
    ax.set_title("RQ1: Coverage vs reference pool")
    ax.set_ylim(0, 1)
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "rq1_coverage.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_rq2(out_dir: Path) -> Path | None:
    data = _load_latest("rq2")
    if not data:
        return None
    rows = data.get("rows") or []
    grounding = [r["with_critic"]["evidence_grounding_rate"] for r in rows]
    fake_nc = [r["no_critic"]["fake_citation_rate"]["fake_rate"] for r in rows]
    fake_wc = [r["with_critic"]["fake_citation_rate"]["fake_rate"] for r in rows]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    g = mean_std(grounding)
    axes[0].bar(["With Critic"], [g["mean"]], yerr=[g["std"]], capsize=6, color="#e76f51")
    axes[0].set_ylim(0, 1)
    axes[0].set_title("Evidence Grounding Rate")

    x = np.arange(2)
    fn = mean_std(fake_nc)
    fw = mean_std(fake_wc)
    axes[1].bar(
        x - 0.15,
        [fn["mean"], fw["mean"]],
        width=0.3,
        yerr=[fn["std"], fw["std"]],
        label="fake_rate",
        color=["#adb5bd", "#2a9d8f"],
    )
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(["No Critic", "With Critic"])
    axes[1].set_ylim(0, 1)
    axes[1].set_title("Fake Citation Rate")
    fig.suptitle("RQ2: Ablation")
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "rq2_ablation.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_rq3(out_dir: Path) -> Path | None:
    data = _load_latest("rq3")
    if not data or not data.get("pipeline"):
        return None
    comp = data["pipeline"]["comparison"]
    w = comp["without_validation"]
    v = comp["with_validation_verified_only"]

    fig, ax = plt.subplots(figsize=(6, 4))
    labels = ["Without validation\n(all citations)", "With validation\n(verified only)"]
    rates = [w["fake_rate"], v["fake_rate"]]
    ax.bar(labels, rates, color=["#e63946", "#2a9d8f"])
    ax.set_ylim(0, max(0.35, max(rates) * 1.2))
    ax.set_ylabel("Fake citation rate (not_found / total)")
    ax.set_title("RQ3: System-level fake citation reduction")
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "rq3_fake_citation.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def generate_all_figures(out_dir: Path | None = None) -> list[str]:
    out_dir = out_dir or Path("results/experiments/figures")
    paths: list[str] = []
    for fn in (plot_rq1, plot_rq2, plot_rq3):
        p = fn(out_dir)
        if p:
            paths.append(str(p))
    return paths
