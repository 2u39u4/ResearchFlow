"""Markdown summary for RQ evaluation experiment outputs."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from eval.analysis.stats import (
    binomial_test_vs_half,
    ci95,
    format_mean_ci,
    mean_std,
    mean_std_ci,
    paired_ttest,
)
from eval.experiments.rq1 import aggregate_rq1
from eval.judges.human_anchor import DEFAULT_CSV, compute_agreement

EXPERIMENT_SUMMARY_PATH = Path("results/experiments/experiment_summary.md")


def _load(rq: str) -> dict[str, Any] | None:
    path = Path("results/experiments") / rq / "latest.json"
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _sig_label(p: float | None, *, alpha: float = 0.05) -> str:
    if p is None:
        return "n/a"
    return "significant" if p < alpha else "not significant"


def build_markdown() -> str:
    lines = ["# Athena Evaluation Summary (RQ1 / RQ2 / RQ3)", ""]
    lines.append(
        "Stats: paired two-sided *t*-tests on matched topic/repeat rows; "
        "95% CIs are normal-approx (mean ± 1.96×SE). α=0.05. "
        "No multiple-comparison correction."
    )
    lines.append("")

    r1 = _load("rq1")
    if r1:
        summary = aggregate_rq1(r1)
        rows = r1.get("rows") or []
        lines.append("## RQ1: Multi-Agent vs Single-Agent")
        lines.append(f"- Runs: {len(rows)} (repeats={r1.get('repeats')})")
        cm, cs = summary["coverage_multi"], summary["coverage_single"]
        lines.append(f"- Coverage multi: {format_mean_ci(cm)}")
        lines.append(f"- Coverage single: {format_mean_ci(cs)}")
        if "depth_multi" in summary:
            dm, ds = summary["depth_multi"], summary["depth_single"]
            lines.append(f"- Depth multi: {format_mean_ci(dm, decimals=2)}")
            lines.append(f"- Depth single: {format_mean_ci(ds, decimals=2)}")
            win_rate = summary.get("pairwise_win_rate_multi", 0)
            wins = sum(1 for r in rows if r.get("pairwise", {}).get("winner") == "multi_agent")
            n_pw = len(rows)
            se_pw = math.sqrt(win_rate * (1 - win_rate) / n_pw) if n_pw else 0.0
            lo, hi = win_rate - 1.96 * se_pw, win_rate + 1.96 * se_pw
            lines.append(
                f"- Pairwise win rate (multi): {win_rate:.1%} "
                f"(n={len(rows)}, 95% CI [{lo:.1%}, {hi:.1%}])"
            )
            bt = binomial_test_vs_half(wins, len(rows))
            if bt["pvalue"] is not None:
                lines.append(f"- Binomial test vs 50%: p={bt['pvalue']:.4f} ({_sig_label(bt['pvalue'])})")
        if rows:
            cov_m = [r["coverage"]["multi_agent"] for r in rows]
            cov_s = [r["coverage"]["single_agent"] for r in rows]
            tt_cov = paired_ttest(cov_m, cov_s)
            diff_cov = mean_std_ci([a - b for a, b in zip(cov_m, cov_s)])
            if tt_cov["pvalue"] is not None:
                lines.append(
                    f"- Paired *t*-test (coverage multi − single): "
                    f"p={tt_cov['pvalue']:.2e} ({_sig_label(tt_cov['pvalue'])})"
                )
                lines.append(
                    f"- Coverage difference: {format_mean_ci(diff_cov)} "
                    "(positive → multi higher)"
                )
            if "depth" in rows[0]:
                dm = [r["depth"]["multi_agent"] for r in rows]
                ds = [r["depth"]["single_agent"] for r in rows]
                tt_d = paired_ttest(dm, ds)
                diff_d = mean_std_ci([a - b for a, b in zip(dm, ds)])
                if tt_d["pvalue"] is not None:
                    lines.append(
                        f"- Paired *t*-test (depth multi − single): "
                        f"p={tt_d['pvalue']:.2e} ({_sig_label(tt_d['pvalue'])})"
                    )
                    lines.append(
                        f"- Depth difference: {format_mean_ci(diff_d, decimals=2)} "
                        "(positive → multi higher)"
                    )
        lines.append("")

    r2 = _load("rq2")
    if r2:
        rows = r2.get("rows") or []
        repeats = int(r2.get("repeats") or 1)
        expected_topics = len([t for t in (r2.get("topic_ids") or [])]) or r2.get("topic_count")
        if expected_topics is None:
            from eval.experiments.common import list_topics

            expected_topics = len([t for t in list_topics(pools_only=True)])
        expected_rows = int(expected_topics) * repeats
        lines.append("## RQ2: Critic ablation")
        lines.append(f"- Runs: {len(rows)} (repeats={repeats})")
        if len(rows) < expected_rows:
            lines.append(
                f"- **WARNING: incomplete RQ2** — expected ~{expected_rows} rows, got {len(rows)}; "
                "re-run rq2 before trusting this section"
            )
        g = mean_std([r["with_critic"]["evidence_grounding_rate"] for r in rows])
        fn = mean_std([r["no_critic"]["fake_citation_rate"]["fake_rate"] for r in rows])
        fw = mean_std([r["with_critic"]["fake_citation_rate"]["fake_rate"] for r in rows])
        lines.append(f"- Evidence grounding (with critic): {format_mean_ci(g)}")
        lines.append(f"- Fake rate no critic: {format_mean_ci(fn)}")
        lines.append(f"- Fake rate with critic: {format_mean_ci(fw)}")
        if rows:
            fake_nc = [r["no_critic"]["fake_citation_rate"]["fake_rate"] for r in rows]
            fake_wc = [r["with_critic"]["fake_citation_rate"]["fake_rate"] for r in rows]
            tt_fake = paired_ttest(fake_nc, fake_wc)
            diff_fake = mean_std_ci([a - b for a, b in zip(fake_nc, fake_wc)])
            if tt_fake["pvalue"] is not None:
                lines.append(
                    f"- Paired *t*-test (fake rate no critic − with critic): "
                    f"p={tt_fake['pvalue']:.4f} ({_sig_label(tt_fake['pvalue'])})"
                )
                lines.append(
                    f"- Fake-rate difference: {format_mean_ci(diff_fake)} "
                    "(positive → no critic lower / critic helps)"
                )
            if "gap_depth" in rows[0]:
                dn = [r["gap_depth"]["no_critic"] for r in rows]
                dw = [r["gap_depth"]["with_critic"] for r in rows]
                lines.append(f"- Depth no critic: {format_mean_ci(mean_std(dn), decimals=2)}")
                lines.append(f"- Depth with critic: {format_mean_ci(mean_std(dw), decimals=2)}")
                tt_depth = paired_ttest(dn, dw)
                diff_depth = mean_std_ci([a - b for a, b in zip(dn, dw)])
                if tt_depth["pvalue"] is not None:
                    lines.append(
                        f"- Paired *t*-test (depth no critic − with critic): "
                        f"p={tt_depth['pvalue']:.4f} ({_sig_label(tt_depth['pvalue'])})"
                    )
                    lines.append(
                        f"- Depth difference: {format_mean_ci(diff_depth, decimals=2)} "
                        "(positive → no critic deeper)"
                    )
        lines.append("")

    r3 = _load("rq3")
    if r3:
        lines.append("## RQ3: Citation validation")
        h = r3.get("hallmark")
        if h:
            lines.append(f"- HALLMARK F1-H: {h.get('f1_hallucination', 0):.3f}")
            lines.append(f"- Detection rate: {h.get('detection_rate', 0):.3f}")
            lines.append(f"- Tier-weighted F1: {h.get('tier_weighted_f1', 0):.3f}")
            lines.append(f"- ECE: {h.get('ece', 0):.3f}")
        p = r3.get("pipeline")
        if p:
            comp = p["comparison"]["without_validation"]
            comp2 = p["comparison"]["with_validation_verified_only"]
            lines.append(
                f"- Pipeline fake rate (no filter): {comp['fake_rate']:.1%} ({comp['total']} citations)"
            )
            lines.append(f"- Pipeline fake rate (verified-only): {comp2['fake_rate']:.1%}")
        lines.append("")

    lines.append("## Significance at a glance (α=0.05)")
    lines.append("| Claim | Result |")
    lines.append("|-------|--------|")
    if r1 and r1.get("rows"):
        rows = r1["rows"]
        cov_m = [r["coverage"]["multi_agent"] for r in rows]
        cov_s = [r["coverage"]["single_agent"] for r in rows]
        tt = paired_ttest(cov_m, cov_s)
        lines.append(
            f"| Multi Coverage > Single | **{_sig_label(tt['pvalue'])}** (p={tt['pvalue']:.2e}) |"
            if tt["pvalue"] is not None
            else "| Multi Coverage > Single | n/a |"
        )
        if "depth" in rows[0]:
            tt = paired_ttest(
                [r["depth"]["multi_agent"] for r in rows],
                [r["depth"]["single_agent"] for r in rows],
            )
            lines.append(
                f"| Multi Depth > Single | **{_sig_label(tt['pvalue'])}** "
                f"(favors single, p={tt['pvalue']:.2e}) |"
                if tt["pvalue"] is not None
                else "| Multi Depth > Single | n/a |"
            )
        wins = sum(1 for r in rows if r.get("pairwise", {}).get("winner") == "multi_agent")
        bt = binomial_test_vs_half(wins, len(rows))
        lines.append(
            f"| Pairwise preference for multi | {_sig_label(bt['pvalue'])} (p={bt['pvalue']:.4f}) |"
            if bt["pvalue"] is not None
            else "| Pairwise preference for multi | n/a |"
        )
    if r2 and r2.get("rows"):
        rows = r2["rows"]
        tt = paired_ttest(
            [r["no_critic"]["fake_citation_rate"]["fake_rate"] for r in rows],
            [r["with_critic"]["fake_citation_rate"]["fake_rate"] for r in rows],
        )
        lines.append(
            f"| Critic lowers fake citation rate | {_sig_label(tt['pvalue'])} (p={tt['pvalue']:.4f}) |"
            if tt["pvalue"] is not None
            else "| Critic lowers fake citation rate | n/a |"
        )
        if "gap_depth" in rows[0]:
            tt = paired_ttest(
                [r["gap_depth"]["no_critic"] for r in rows],
                [r["gap_depth"]["with_critic"] for r in rows],
            )
            lines.append(
                f"| Critic improves depth | **{_sig_label(tt['pvalue'])}** "
                f"(favors no critic, p={tt['pvalue']:.4f}) |"
                if tt["pvalue"] is not None
                else "| Critic improves depth | n/a |"
            )
    lines.append("| Validator removes pipeline fake cites | descriptive (n=18 pipeline cites) |")
    lines.append("")

    anchor_stats = compute_agreement(DEFAULT_CSV)
    if anchor_stats.get("n_human_rows"):
        lines.append("## Human anchor vs LLM judge")
        lines.append(f"- Sample: {anchor_stats['n_human_rows']} rows (~20% stratified, repeat=0)")
        lines.append(f"- CSV: `{DEFAULT_CSV}`")
        km = anchor_stats.get("depth_multi_kappa")
        ks = anchor_stats.get("depth_single_kappa")
        rm = anchor_stats.get("depth_multi_spearman")
        ka = anchor_stats.get("depth_a_kappa")
        ra = anchor_stats.get("depth_a_spearman")
        pa = anchor_stats.get("preference_agreement_rate")
        if km is not None:
            lines.append(f"- Depth (multi) Cohen's κ: {km:.3f}")
        if ks is not None:
            lines.append(f"- Depth (single) Cohen's κ: {ks:.3f}")
        if rm is not None:
            lines.append(f"- Depth (multi) Spearman ρ: {rm:.3f}")
        elif ka is not None:
            lines.append(f"- Depth A Cohen's κ: {ka:.3f}")
            if ra is not None:
                lines.append(f"- Depth A Spearman ρ: {ra:.3f}")
        if pa is not None:
            lines.append(f"- Preference agreement: {pa:.1%} (n={anchor_stats.get('n_preference', 0)})")
        lines.append("")

    return "\n".join(lines)


def write_report(path: Path | None = None) -> Path:
    path = path or EXPERIMENT_SUMMARY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_markdown(), encoding="utf-8")
    return path
