"""Pipeline step trace logs."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class StepLog(BaseModel):
    step: str
    agent: str
    summary: str
    payload: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
