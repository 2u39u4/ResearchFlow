"""Reusable Streamlit UI helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

STATUS_STYLES = {
    "verified": ("✅", "Verified", "#d4edda"),
    "not_found": ("❌", "Not found", "#f8d7da"),
    "mismatch": ("⚠️", "Mismatch", "#fff3cd"),
}

CRITIQUE_TYPE_LABELS = {
    "gap": "Research gap",
    "weakness": "Weakness",
    "novelty": "Relative novelty",
}


def render_integrity_banner() -> None:
    st.warning(
        "**Academic integrity** — Athena is a *research assistance* tool. It does not ghost-write "
        "submittable manuscripts or replace author writing, analysis, or authorship. "
        "Outlines include `[TODO: author to complete]` markers for human completion.",
        icon="⚖️",
    )


def status_badge(status: str) -> str:
    icon, label, _ = STATUS_STYLES.get(status, ("❓", status, "#eee"))
    return f"{icon} **{label}**"


def papers_by_id(papers: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p["paper_id"]: p for p in papers if p.get("paper_id")}


def render_paper_card(paper: dict[str, Any]) -> None:
    authors = ", ".join(paper.get("authors") or [])[:120]
    st.markdown(f"**{paper.get('title', 'Untitled')}**")
    meta = []
    if paper.get("year"):
        meta.append(str(paper["year"]))
    if paper.get("venue"):
        meta.append(paper["venue"])
    if paper.get("doi"):
        meta.append(f"DOI: `{paper['doi']}`")
    if meta:
        st.caption(" · ".join(meta))
    if authors:
        st.caption(authors)
    if paper.get("abstract"):
        abstract = paper["abstract"]
        if len(abstract) > 400:
            abstract = abstract[:397] + "..."
        st.text(abstract)


def trace_timings(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    prev: datetime | None = None
    for entry in trace:
        ts_raw = entry.get("created_at", "")
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            ts = None
        duration = None
        if ts and prev:
            duration = (ts - prev).total_seconds()
        prev = ts if ts else prev
        rows.append(
            {
                "step": entry.get("step"),
                "agent": entry.get("agent"),
                "summary": entry.get("summary"),
                "duration_sec": round(duration, 2) if duration is not None else None,
            }
        )
    return rows
