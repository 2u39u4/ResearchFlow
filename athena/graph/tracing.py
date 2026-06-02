"""Append trace entries to graph state."""

from __future__ import annotations

from typing import Any

from athena.schemas.trace import StepLog


def append_trace(
    state: dict[str, Any],
    *,
    step: str,
    agent: str,
    summary: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    log = StepLog(
        step=step,
        agent=agent,
        summary=summary,
        payload=payload or {},
    )
    existing = list(state.get("trace") or [])
    existing.append(log.model_dump())
    return {"trace": existing}
