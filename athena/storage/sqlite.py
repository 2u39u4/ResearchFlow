"""SQLite persistence for papers, tasks, citations, and experiment traces."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

from athena.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL,
    task_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    citation_json TEXT NOT NULL,
    source_run_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    citation_id INTEGER,
    status TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (citation_id) REFERENCES citations(id)
);

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    result_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trace (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    step TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: str | None = None) -> None:
    settings = get_settings()
    settings.ensure_dirs()
    path = db_path or str(settings.athena_db_path)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_db(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    settings = get_settings()
    path = db_path or str(settings.athena_db_path)
    init_db(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_sample_records() -> dict[str, Any]:
    """Insert one sample row per table for smoke / integration checks."""
    run_id = "smoke-run-001"
    now = _utc_now()
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO papers (paper_id, title, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                "arxiv:2401.00001",
                "Sample Paper",
                json.dumps({"source": "smoke"}),
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO tasks (topic, task_json, status, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("graph rag", json.dumps([{"id": 1, "name": "search"}]), "done", now),
        )
        cur = conn.execute(
            """
            INSERT INTO citations (citation_json, source_run_id, created_at)
            VALUES (?, ?, ?)
            """,
            (json.dumps({"title": "Attention Is All You Need"}), run_id, now),
        )
        citation_id = cur.lastrowid
        conn.execute(
            """
            INSERT INTO validation_results (citation_id, status, detail_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (citation_id, "verified", json.dumps({"note": "smoke"}), now),
        )
        conn.execute(
            """
            INSERT INTO experiments (name, config_json, result_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            ("smoke", json.dumps({"rq": "smoke"}), json.dumps({"ok": True}), now),
        )
        conn.execute(
            """
            INSERT INTO trace (run_id, step, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (run_id, "init", json.dumps({"message": "smoke"}), now),
        )
    return {"run_id": run_id, "citation_id": citation_id}


def persist_traces(run_id: str, traces: list[dict[str, Any]], db_path: str | None = None) -> int:
    """Write pipeline trace steps to the trace table."""
    if not run_id or not traces:
        return 0
    now = _utc_now()
    count = 0
    with get_db(db_path) as conn:
        for entry in traces:
            step = entry.get("step", "unknown")
            conn.execute(
                """
                INSERT INTO trace (run_id, step, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, step, json.dumps(entry, ensure_ascii=False), now),
            )
            count += 1
    return count
