"""Safe handling for Streamlit file uploads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_MAX_JSON_BYTES = 5 * 1024 * 1024  # 5 MiB


def safe_upload_basename(name: str) -> str:
    """Return a single path segment; reject traversal and empty names."""
    if not name or ".." in name or "/" in name or "\\" in name:
        raise ValueError("Invalid upload filename")
    base = Path(name).name.strip()
    if not base or base in {".", ".."}:
        raise ValueError("Invalid upload filename")
    return base


def resolve_upload_path(directory: Path, filename: str) -> Path:
    """Resolve destination under directory; raise if it escapes."""
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    dest = (directory / safe_upload_basename(filename)).resolve()
    if dest.parent != directory:
        raise ValueError("Upload path escapes target directory")
    return dest


def load_bounded_json(raw: bytes, *, max_bytes: int = DEFAULT_MAX_JSON_BYTES) -> dict[str, Any]:
    if len(raw) > max_bytes:
        raise ValueError(f"JSON file exceeds {max_bytes // (1024 * 1024)} MiB limit")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Report JSON must be an object at the top level")
    return data
