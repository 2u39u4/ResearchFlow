"""Upload safety helpers for Streamlit."""

import json
from pathlib import Path

import pytest

from app.upload_utils import load_bounded_json, resolve_upload_path, safe_upload_basename


def test_safe_upload_basename_rejects_traversal():
    with pytest.raises(ValueError):
        safe_upload_basename("../evil.pdf")
    with pytest.raises(ValueError):
        safe_upload_basename("")
    assert safe_upload_basename("paper.pdf") == "paper.pdf"


def test_resolve_upload_path_stays_in_directory(tmp_path):
    dest = resolve_upload_path(tmp_path, "notes.pdf")
    assert dest.parent == tmp_path.resolve()
    with pytest.raises(ValueError):
        resolve_upload_path(tmp_path, "../../outside.pdf")


def test_load_bounded_json_enforces_size():
    payload = json.dumps({"ok": True}).encode()
    assert load_bounded_json(payload, max_bytes=1024)["ok"] is True
    with pytest.raises(ValueError):
        load_bounded_json(b"x" * 10, max_bytes=5)
