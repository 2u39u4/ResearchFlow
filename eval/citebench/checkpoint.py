"""Checkpoint helpers for resumable HALLMARK batch evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class BatchCheckpointState:
    """Metadata for a resumable HALLMARK eval run."""

    version: int
    split: str
    tool_name: str
    delay_seconds: float
    batch_size: int
    total_entries: int
    completed_count: int
    last_batch_index: int
    updated_at: str

    @classmethod
    def fresh(
        cls,
        *,
        split: str,
        tool_name: str,
        delay_seconds: float,
        batch_size: int,
        total_entries: int,
    ) -> BatchCheckpointState:
        return cls(
            version=1,
            split=split,
            tool_name=tool_name,
            delay_seconds=delay_seconds,
            batch_size=batch_size,
            total_entries=total_entries,
            completed_count=0,
            last_batch_index=-1,
            updated_at=_utc_now(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BatchCheckpointState:
        return cls(
            version=int(data["version"]),
            split=str(data["split"]),
            tool_name=str(data["tool_name"]),
            delay_seconds=float(data["delay_seconds"]),
            batch_size=int(data["batch_size"]),
            total_entries=int(data["total_entries"]),
            completed_count=int(data["completed_count"]),
            last_batch_index=int(data["last_batch_index"]),
            updated_at=str(data["updated_at"]),
        )


def checkpoint_paths(checkpoint_dir: Path) -> dict[str, Path]:
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    batches = checkpoint_dir / "batches"
    batches.mkdir(parents=True, exist_ok=True)
    return {
        "root": checkpoint_dir,
        "state": checkpoint_dir / "state.json",
        "predictions": checkpoint_dir / "predictions.jsonl",
        "batches": batches,
        "merged_metrics": checkpoint_dir / "merged_metrics.json",
    }


def load_state(path: Path) -> BatchCheckpointState | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text())
    return BatchCheckpointState.from_dict(data)


def save_state(path: Path, state: BatchCheckpointState) -> None:
    state.updated_at = _utc_now()
    path.write_text(json.dumps(state.to_dict(), indent=2, ensure_ascii=False) + "\n")


def load_predictions_jsonl(path: Path) -> dict[str, Any]:
    """Return bibtex_key -> Prediction dict (HALLMARK schema)."""
    preds: dict[str, Any] = {}
    if not path.is_file():
        return preds
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        key = data.get("bibtex_key")
        if key:
            preds[key] = data
    return preds


def append_prediction_jsonl(path: Path, prediction_dict: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(prediction_dict, ensure_ascii=False) + "\n")
        fh.flush()


def batch_result_path(batches_dir: Path, batch_index: int, end_index: int) -> Path:
    return batches_dir / f"batch_{batch_index:03d}_upto_{end_index:04d}.json"


def reset_checkpoint(checkpoint_dir: Path) -> None:
    paths = checkpoint_paths(checkpoint_dir)
    for key in ("state", "predictions", "merged_metrics"):
        p = paths[key]
        if p.is_file():
            p.unlink()
    if paths["batches"].is_dir():
        for child in paths["batches"].glob("batch_*.json"):
            child.unlink()
