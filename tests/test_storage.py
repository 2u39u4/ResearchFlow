"""Storage and cache unit tests — no network."""

import json
import tempfile
from pathlib import Path

from athena.storage.cache import clear_llm_cache, get_llm_cache, make_cache_key
from athena.storage.sqlite import get_db, init_db, insert_sample_records


def test_cache_key_stable():
    msgs = [{"role": "user", "content": "hi"}]
    k1 = make_cache_key(msgs, "gpt-4o-mini", temperature=0.2)
    k2 = make_cache_key(msgs, "gpt-4o-mini", temperature=0.2)
    assert k1 == k2


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("ATHENA_CACHE_DIR", str(tmp_path / "cache"))
    clear_llm_cache()
    cache = get_llm_cache()
    cache["test-key"] = "hello"
    assert cache["test-key"] == "hello"
    assert clear_llm_cache() >= 0


def test_sqlite_tables(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("ATHENA_DB_PATH", str(db))
    init_db(str(db))
    insert_sample_records()
    with get_db(str(db)) as conn:
        n = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    assert n >= 1
