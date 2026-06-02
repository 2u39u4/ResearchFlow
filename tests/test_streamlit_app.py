"""Smoke tests for Streamlit app helpers (no browser)."""

from __future__ import annotations

from app.components import papers_by_id, status_badge, trace_timings


def test_status_badge():
    assert "Verified" in status_badge("verified")
    assert "Not found" in status_badge("not_found")


def test_papers_by_id():
    idx = papers_by_id([{"paper_id": "a:1", "title": "T"}])
    assert idx["a:1"]["title"] == "T"


def test_trace_timings():
    trace = [
        {"step": "planner", "agent": "planner", "summary": "ok", "created_at": "2026-01-01T00:00:00+00:00"},
        {"step": "research", "agent": "research", "summary": "ok", "created_at": "2026-01-01T00:00:05+00:00"},
    ]
    rows = trace_timings(trace)
    assert rows[1]["duration_sec"] == 5.0
