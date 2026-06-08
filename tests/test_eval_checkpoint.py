"""Checkpoint helpers for RQ1/RQ2 per-topic persistence."""

from __future__ import annotations

from pathlib import Path

from eval.experiments.common import (
    resume_rows,
    save_topic_checkpoint,
    topic_is_complete,
    upsert_row,
)


def test_upsert_and_topic_complete():
    rows = [{"topic_id": "t01", "repeat": 0}]
    rows = upsert_row(rows, {"topic_id": "t01", "repeat": 0, "v": 2})
    assert len(rows) == 1
    assert rows[0]["v"] == 2
    rows = upsert_row(rows, {"topic_id": "t01", "repeat": 1})
    assert topic_is_complete(rows, "t01", 2)
    assert not topic_is_complete(rows, "t02", 1)


def test_save_topic_checkpoint_writes_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "eval.experiments.common.RESULTS_ROOT",
        tmp_path,
    )
    payload = {
        "rq": "RQ2",
        "repeats": 3,
        "skip_judge": False,
        "rows": [
            {"topic_id": "t01", "repeat": 0},
            {"topic_id": "t02", "repeat": 0},
        ],
    }
    save_topic_checkpoint("rq2", payload, "t01")
    assert (tmp_path / "rq2" / "by_topic" / "t01.json").is_file()
    assert (tmp_path / "rq2" / "checkpoint.json").is_file()
    assert (tmp_path / "rq2" / "latest.json").is_file()
    rows, _ = resume_rows("rq2", repeats=3, skip_judge=False)
    assert len(rows) == 2
