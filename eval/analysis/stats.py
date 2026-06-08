"""Descriptive stats and agreement metrics for RQ evaluation experiments."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Sequence

import numpy as np


def mean_std(values: Sequence[float]) -> dict[str, float]:
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return {"mean": 0.0, "std": 0.0, "n": 0}
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        "n": int(arr.size),
    }


def ci95(mean: float, std: float, n: int) -> tuple[float, float]:
    """Normal-approx 95% CI for the mean (mean ± 1.96 × SE)."""
    if n <= 1:
        return (mean, mean)
    se = std / math.sqrt(n)
    margin = 1.96 * se
    return (mean - margin, mean + margin)


def mean_std_ci(values: Sequence[float]) -> dict[str, float]:
    ms = mean_std(values)
    lo, hi = ci95(ms["mean"], ms["std"], ms["n"])
    return {**ms, "ci95_lo": lo, "ci95_hi": hi}


def format_mean_ci(ms: dict[str, float], *, decimals: int = 3) -> str:
    lo, hi = ci95(ms["mean"], ms["std"], ms["n"])
    return (
        f"{ms['mean']:.{decimals}f} ± {ms['std']:.{decimals}f} "
        f"(n={ms['n']}, 95% CI [{lo:.{decimals}f}, {hi:.{decimals}f}])"
    )


def binomial_test_vs_half(successes: int, n: int) -> dict[str, float | None]:
    if n <= 0:
        return {"pvalue": None, "n": 0}
    try:
        from scipy import stats

        res = stats.binomtest(successes, n, 0.5, alternative="two-sided")
        return {"pvalue": float(res.pvalue), "n": n}
    except Exception:
        return {"pvalue": None, "n": n}


def paired_ttest(a: Sequence[float], b: Sequence[float]) -> dict[str, float | None]:
    """Paired two-sided t-test (SciPy if available)."""
    a_arr = np.asarray(list(a), dtype=float)
    b_arr = np.asarray(list(b), dtype=float)
    if a_arr.size != b_arr.size or a_arr.size < 2:
        return {"statistic": None, "pvalue": None, "n": int(min(a_arr.size, b_arr.size))}
    try:
        from scipy import stats

        res = stats.ttest_rel(a_arr, b_arr)
        return {
            "statistic": float(res.statistic),
            "pvalue": float(res.pvalue),
            "n": int(a_arr.size),
        }
    except Exception:
        return {"statistic": None, "pvalue": None, "n": int(a_arr.size)}


def cohens_kappa(labels_a: Sequence[int], labels_b: Sequence[int]) -> float | None:
    if len(labels_a) != len(labels_b) or len(labels_a) == 0:
        return None
    from collections import Counter

    pairs = list(zip(labels_a, labels_b))
    n = len(pairs)
    agree = sum(1 for x, y in pairs if x == y) / n
    pa = agree
    ca, cb = Counter(labels_a), Counter(labels_b)
    pe = sum(ca[k] / n * cb[k] / n for k in set(ca) | set(cb))
    if math.isclose(1 - pe, 0.0):
        return None
    return (pa - pe) / (1 - pe)


def spearman_rho(a: Sequence[float], b: Sequence[float]) -> float | None:
    if len(a) != len(b) or len(a) < 2:
        return None
    try:
        from scipy import stats

        res = stats.spearmanr(a, b)
        return float(res.correlation)
    except Exception:
        return None


def load_human_anchor_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def human_anchor_agreement(
    human_rows: list[dict[str, str]],
    llm_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare human CSV columns to LLM judge rows keyed by sample_id.
    Supports system-labeled columns (depth_multi_1to5 / depth_single_1to5) or
    legacy blind columns (depth_a_1to5 / depth_b_1to5).
    """
    depth_pairs_multi: list[tuple[int, int]] = []
    depth_pairs_single: list[tuple[int, int]] = []
    depth_pairs_a: list[tuple[int, int]] = []
    depth_pairs_b: list[tuple[int, int]] = []
    pref_match = 0
    pref_n = 0

    for row in human_rows:
        sid = row.get("sample_id", "").strip()
        if not sid or sid not in llm_rows:
            continue
        llm = llm_rows[sid]
        try:
            if row.get("depth_multi_1to5") or row.get("depth_single_1to5"):
                hm = int(row.get("depth_multi_1to5") or 0)
                hs = int(row.get("depth_single_1to5") or 0)
                lm = int(llm.get("depth_multi", 0))
                ls = int(llm.get("depth_single", 0))
                if hm and lm:
                    depth_pairs_multi.append((hm, lm))
                if hs and ls:
                    depth_pairs_single.append((hs, ls))
            else:
                ha = int(row.get("depth_a_1to5") or 0)
                hb = int(row.get("depth_b_1to5") or 0)
                la = int(llm.get("depth_a", 0))
                lb = int(llm.get("depth_b", 0))
                if ha and la:
                    depth_pairs_a.append((ha, la))
                if hb and lb:
                    depth_pairs_b.append((hb, lb))
        except ValueError:
            continue

        human_pref = (
            (row.get("preference_multi_single_tie") or row.get("preference_a_b_tie") or "")
            .strip()
            .lower()
        )
        llm_pref = (llm.get("preference") or "").strip().lower()
        if human_pref and llm_pref:
            pref_n += 1
            if human_pref == llm_pref:
                pref_match += 1

    out: dict[str, Any] = {
        "preference_agreement_rate": pref_match / pref_n if pref_n else None,
        "n_preference": pref_n,
    }
    if depth_pairs_multi:
        out["depth_multi_kappa"] = cohens_kappa(
            [x[0] for x in depth_pairs_multi], [x[1] for x in depth_pairs_multi]
        )
        out["depth_single_kappa"] = cohens_kappa(
            [x[0] for x in depth_pairs_single], [x[1] for x in depth_pairs_single]
        )
        out["depth_multi_spearman"] = spearman_rho(
            [x[0] for x in depth_pairs_multi], [x[1] for x in depth_pairs_multi]
        )
        out["n_depth_pairs"] = len(depth_pairs_multi)
    else:
        out["depth_a_kappa"] = cohens_kappa(
            [x[0] for x in depth_pairs_a], [x[1] for x in depth_pairs_a]
        )
        out["depth_b_kappa"] = cohens_kappa(
            [x[0] for x in depth_pairs_b], [x[1] for x in depth_pairs_b]
        )
        out["depth_a_spearman"] = spearman_rho(
            [x[0] for x in depth_pairs_a], [x[1] for x in depth_pairs_a]
        )
        out["n_depth_pairs"] = len(depth_pairs_a)
    return out
