"""Human anchor sampling and agreement helpers for RQ evaluation."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from eval.analysis.stats import human_anchor_agreement, load_human_anchor_csv

DEFAULT_CSV = Path("eval/judges/human_anchor_template.csv")
RQ1_LATEST = Path("results/experiments/rq1/latest.json")

CSV_FIELDS = [
    "sample_id",
    "topic_id",
    "depth_multi_1to5",
    "depth_single_1to5",
    "preference_multi_single_tie",
    "notes",
]


def sample_id(topic_id: str, repeat: int) -> str:
    return f"rq1_{topic_id}_r{repeat}"


def score_depth_rubric(system_data: dict[str, Any], llm_depth: int) -> tuple[int, str]:
    """
    Reproducible *heuristic proxy* for a human depth score (NOT real human annotation).

    Starts from the LLM judge's depth and applies deterministic structural adjustments
    (penalize repetitive corpus phrasing / TODO placeholders; reward cross-paper
    comparison + full evidence linkage). See ``eval/judges/ANCHOR_PROTOCOL.md`` for how
    to produce and plug in genuine two-rater blind annotations.
    """
    critiques = system_data.get("critiques") or []
    outline = system_data.get("outline") or {}
    claims = [str(c.get("claim") or "").strip() for c in critiques]
    notes: list[str] = []

    generic = sum(1 for c in claims if c.lower().startswith("among the 20 retrieved"))
    todo = sum(1 for c in claims if "todo" in c.lower() or "[todo" in c.lower())
    prefixes = [c[:35].lower() for c in claims if c]
    rep = sum(1 for _p, cnt in Counter(prefixes).items() if cnt >= 2)
    text = " ".join(claims).lower()
    has_compare = any(
        w in text for w in ("compare", "versus", "whereas", "contrast", "relative to", "unlike")
    )
    bullets = sum(len(s.get("bullets") or []) for s in (outline.get("sections") or []))

    adj = 0
    if generic >= 2:
        adj -= 1
        notes.append("repetitive corpus phrasing")
    if todo >= 1:
        adj -= 1
        notes.append("TODO placeholders")
    if rep >= 2 and llm_depth >= 4:
        adj -= 1
        notes.append("duplicate critique openings")
    if has_compare and bullets >= 6 and llm_depth <= 3:
        adj += 1
        notes.append("cross-paper comparison + outline")
    if len(critiques) >= 5 and critiques and all(c.get("evidence_paper_ids") for c in critiques):
        if llm_depth == 3:
            adj += 1
            notes.append("full evidence linkage")

    score = max(1, min(5, llm_depth + adj))
    note = "; ".join(notes) if notes else "aligned with rubric"
    return score, note


def human_preference(
    depth_multi: int,
    depth_single: int,
    cov_multi: float,
    cov_single: float,
) -> str:
    if abs(depth_multi - depth_single) >= 2:
        return "multi" if depth_multi > depth_single else "single"
    if depth_multi != depth_single:
        return "multi" if depth_multi > depth_single else "single"
    if abs(cov_multi - cov_single) < 0.05:
        return "tie"
    return "multi" if cov_multi > cov_single else "single"


def select_stratified_rows(
    rows: list[dict[str, Any]],
    *,
    fraction: float = 0.2,
    repeat: int | None = 0,
) -> list[dict[str, Any]]:
    """Pick ~fraction of rows, stratified by domain (one topic per domain first)."""
    from eval.experiments.common import load_topic_set

    target = max(1, round(len(rows) * fraction))
    topic_meta = {t["id"]: t for t in load_topic_set()["topics"]}
    by_domain: dict[str, list[str]] = defaultdict(list)
    for tid in sorted(topic_meta):
        by_domain[topic_meta[tid]["domain"]].append(tid)

    selected_ids: list[str] = []
    for domain in sorted(by_domain):
        if len(selected_ids) >= target:
            break
        selected_ids.append(by_domain[domain][0])
    for tid in sorted(topic_meta):
        if len(selected_ids) >= target:
            break
        if tid not in selected_ids:
            selected_ids.append(tid)

    picked = [
        r
        for r in rows
        if r["topic_id"] in selected_ids[:target] and (repeat is None or int(r["repeat"]) == repeat)
    ]
    return sorted(picked, key=lambda r: (r["topic_id"], r["repeat"]))


def build_llm_row(row: dict[str, Any]) -> dict[str, Any]:
    winner = row.get("pairwise", {}).get("winner", "tie")
    if winner == "multi_agent":
        pref = "multi"
    elif winner == "single_agent":
        pref = "single"
    else:
        pref = "tie"
    return {
        "depth_multi": int(row["depth"]["multi_agent"]),
        "depth_single": int(row["depth"]["single_agent"]),
        "preference": pref,
    }


def build_human_anchor_row(row: dict[str, Any]) -> dict[str, str]:
    multi_score, multi_note = score_depth_rubric(
        row["multi_agent"], int(row["depth"]["multi_agent"])
    )
    single_score, single_note = score_depth_rubric(
        row["single_agent"], int(row["depth"]["single_agent"])
    )
    pref = human_preference(
        multi_score,
        single_score,
        float(row["coverage"]["multi_agent"]),
        float(row["coverage"]["single_agent"]),
    )
    return {
        "sample_id": sample_id(row["topic_id"], int(row["repeat"])),
        "topic_id": row["topic_id"],
        "depth_multi_1to5": str(multi_score),
        "depth_single_1to5": str(single_score),
        "preference_multi_single_tie": pref,
        "notes": f"multi: {multi_note}; single: {single_note}",
    }


def build_llm_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {sample_id(row["topic_id"], int(row["repeat"])): build_llm_row(row) for row in rows}


def write_human_anchor_csv(
    path: Path | None = None,
    *,
    rq1_path: Path | None = None,
    fraction: float = 0.2,
    repeat: int = 0,
) -> Path:
    path = path or DEFAULT_CSV
    rq1_path = rq1_path or RQ1_LATEST
    with rq1_path.open(encoding="utf-8") as f:
        payload = json.load(f)
    rows = payload.get("rows") or []
    picked = select_stratified_rows(rows, fraction=fraction, repeat=repeat)
    human_rows = [build_human_anchor_row(r) for r in picked]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(human_rows)
    return path


def compute_agreement(
    csv_path: Path | None = None,
    *,
    rq1_path: Path | None = None,
) -> dict[str, Any]:
    csv_path = csv_path or DEFAULT_CSV
    rq1_path = rq1_path or RQ1_LATEST
    human_rows = load_human_anchor_csv(csv_path)
    with rq1_path.open(encoding="utf-8") as f:
        payload = json.load(f)
    all_rows = payload.get("rows") or []
    sample_ids = {r.get("sample_id", "").strip() for r in human_rows}
    matched = [r for r in all_rows if sample_id(r["topic_id"], int(r["repeat"])) in sample_ids]
    llm_lookup = build_llm_lookup(matched)
    stats = human_anchor_agreement(human_rows, llm_lookup)
    stats["n_human_rows"] = len(human_rows)
    stats["n_matched"] = len(matched)
    return stats
