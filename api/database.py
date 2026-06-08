"""SQLite persistence for users, runs, and library metadata."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from api.config import get_api_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    google_sub TEXT UNIQUE,
    email TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    locale TEXT DEFAULT 'en',
    default_year_min INTEGER,
    default_year_max INTEGER,
    default_domain TEXT,
    deleted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    status TEXT NOT NULL,
    constraints_json TEXT,
    report_json TEXT,
    error_message TEXT,
    paper_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS library_docs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    doc_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, doc_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_path() -> Path:
    settings = get_api_settings()
    settings.athena_data_dir.mkdir(parents=True, exist_ok=True)
    return settings.athena_db_path


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    path = db_path()
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def upsert_user(
    *,
    google_sub: str,
    email: str,
    display_name: str | None,
    avatar_url: str | None,
    locale: str = "en",
) -> dict[str, Any]:
    now = utc_now()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE google_sub = ? AND deleted_at IS NULL",
            (google_sub,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE users SET email=?, display_name=?, avatar_url=?, updated_at=?
                WHERE id=?
                """,
                (email, display_name, avatar_url, now, existing["id"]),
            )
            return row_to_dict(
                conn.execute("SELECT * FROM users WHERE id=?", (existing["id"],)).fetchone()
            ) or {}

        user_id = new_id()
        conn.execute(
            """
            INSERT INTO users (id, google_sub, email, display_name, avatar_url, locale, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, google_sub, email, display_name, avatar_url, locale, now, now),
        )
        return row_to_dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()) or {}


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id=? AND deleted_at IS NULL",
            (user_id,),
        ).fetchone()
        return row_to_dict(row)


def get_dev_user() -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE google_sub='dev-local' AND deleted_at IS NULL"
        ).fetchone()
        if row:
            return row_to_dict(row) or {}
        return upsert_user(
            google_sub="dev-local",
            email="dev@local.test",
            display_name="Dev User",
            avatar_url=None,
        )


def update_user(user_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {
        "display_name",
        "locale",
        "default_year_min",
        "default_year_max",
        "default_domain",
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_user_by_id(user_id)
    updates["updated_at"] = utc_now()
    sets = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE users SET {sets} WHERE id=? AND deleted_at IS NULL",
            (*updates.values(), user_id),
        )
        return get_user_by_id(user_id)


def soft_delete_user(user_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET deleted_at=?, updated_at=? WHERE id=?",
            (utc_now(), utc_now(), user_id),
        )


def create_run(user_id: str, topic: str, constraints: dict[str, Any]) -> dict[str, Any]:
    run_id = f"run-{new_id()}"
    now = utc_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO runs (id, user_id, topic, status, constraints_json, created_at)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (run_id, user_id, topic, json.dumps(constraints), now),
        )
    return get_run(run_id, user_id) or {}


def update_run(
    run_id: str,
    *,
    status: str | None = None,
    report: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    fields: dict[str, Any] = {}
    if status is not None:
        fields["status"] = status
    if report is not None:
        fields["report_json"] = json.dumps(report, ensure_ascii=False)
        fields["paper_count"] = len(report.get("papers") or [])
    if error_message is not None:
        fields["error_message"] = error_message
    if status in ("completed", "failed"):
        fields["finished_at"] = utc_now()
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    with get_conn() as conn:
        conn.execute(f"UPDATE runs SET {sets} WHERE id=?", (*fields.values(), run_id))


def get_run(run_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    with get_conn() as conn:
        if user_id:
            row = conn.execute(
                "SELECT * FROM runs WHERE id=? AND user_id=?",
                (run_id, user_id),
            ).fetchone()
        else:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        data = row_to_dict(row)
        if not data:
            return None
        if data.get("constraints_json"):
            data["constraints"] = json.loads(data["constraints_json"])
        if data.get("report_json"):
            data["report"] = json.loads(data["report_json"])
        return data


def list_runs(user_id: str, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, user_id, topic, status, paper_count, error_message, created_at, finished_at
            FROM runs WHERE user_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
        return [row_to_dict(r) or {} for r in rows]


def delete_run(run_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM runs WHERE id=? AND user_id=?", (run_id, user_id))
        return cur.rowcount > 0


def upsert_library_doc(user_id: str, doc_id: str, filename: str, chunk_count: int) -> dict[str, Any]:
    now = utc_now()
    doc_pk = new_id()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO library_docs (id, user_id, doc_id, filename, chunk_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, doc_id) DO UPDATE SET chunk_count=excluded.chunk_count
            """,
            (doc_pk, user_id, doc_id, filename, chunk_count, now),
        )
        row = conn.execute(
            "SELECT * FROM library_docs WHERE user_id=? AND doc_id=?",
            (user_id, doc_id),
        ).fetchone()
        return row_to_dict(row) or {}


def list_library_docs(user_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM library_docs WHERE user_id=? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [row_to_dict(r) or {} for r in rows]


def delete_library_doc(user_id: str, doc_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM library_docs WHERE user_id=? AND doc_id=?",
            (user_id, doc_id),
        )
        return cur.rowcount > 0
