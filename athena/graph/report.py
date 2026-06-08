"""Serialize pipeline state to JSON-friendly dict."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, list):
        return [_dump(v) for v in value]
    if isinstance(value, dict):
        return {k: _dump(v) for k, v in value.items()}
    return value


def state_to_report(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": state.get("run_id"),
        "topic": state.get("topic"),
        "constraints": state.get("constraints") or {},
        "revisions": state.get("revisions") or 0,
        "revision_log": state.get("revision_log") or [],
        "planner_meta": state.get("planner_meta"),
        "tasks": _dump(state.get("tasks") or []),
        "research_errors": state.get("research_errors") or [],
        "research_sources_ok": state.get("research_sources_ok") or {},
        "papers": _dump(state.get("papers") or []),
        "critic_meta": state.get("critic_meta"),
        "critiques": _dump(state.get("critiques") or []),
        "writer_meta": state.get("writer_meta"),
        "draft": _dump(state.get("draft")),
        "citations": _dump(state.get("citations") or []),
        "validation_report": _dump(state.get("validation_report") or []),
        "trace": state.get("trace") or [],
    }
