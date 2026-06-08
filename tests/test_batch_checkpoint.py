"""Offline tests for HALLMARK batch checkpoint helpers."""

from __future__ import annotations

from pathlib import Path

from eval.citebench.checkpoint import (
    BatchCheckpointState,
    append_prediction_jsonl,
    batch_result_path,
    checkpoint_paths,
    load_predictions_jsonl,
    load_state,
    reset_checkpoint,
    save_state,
)


def test_checkpoint_roundtrip(tmp_path: Path):
    paths = checkpoint_paths(tmp_path / "cp")
    state = BatchCheckpointState.fresh(
        split="dev_public",
        tool_name="athena-validator",
        delay_seconds=0.2,
        batch_size=50,
        total_entries=1119,
    )
    state.completed_count = 50
    state.last_batch_index = 0
    save_state(paths["state"], state)

    loaded = load_state(paths["state"])
    assert loaded is not None
    assert loaded.completed_count == 50
    assert loaded.batch_size == 50
    assert loaded.delay_seconds == 0.2


def test_predictions_jsonl_append_and_load(tmp_path: Path):
    paths = checkpoint_paths(tmp_path / "cp")
    pred = {
        "bibtex_key": "key1",
        "label": "VALID",
        "confidence": 0.9,
        "reason": "athena:verified",
    }
    append_prediction_jsonl(paths["predictions"], pred)
    append_prediction_jsonl(
        paths["predictions"],
        {"bibtex_key": "key2", "label": "HALLUCINATED", "confidence": 0.85, "reason": "x"},
    )

    loaded = load_predictions_jsonl(paths["predictions"])
    assert set(loaded) == {"key1", "key2"}
    assert loaded["key1"]["label"] == "VALID"


def test_reset_checkpoint(tmp_path: Path):
    root = tmp_path / "cp"
    paths = checkpoint_paths(root)
    save_state(
        paths["state"],
        BatchCheckpointState.fresh(
            split="dev_public",
            tool_name="athena-validator",
            delay_seconds=0.2,
            batch_size=50,
            total_entries=10,
        ),
    )
    append_prediction_jsonl(
        paths["predictions"],
        {"bibtex_key": "k", "label": "VALID", "confidence": 0.5, "reason": ""},
    )
    batch_result_path(paths["batches"], 0, 50).write_text("{}")

    reset_checkpoint(root)
    assert not paths["state"].exists()
    assert not paths["predictions"].exists()
    assert list(paths["batches"].glob("batch_*.json")) == []


def test_batch_result_path_naming():
    p = batch_result_path(Path("/tmp/b"), 2, 150)
    assert p.name == "batch_002_upto_0150.json"
