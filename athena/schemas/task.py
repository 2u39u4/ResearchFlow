"""Planner task models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal["search", "analyze", "outline", "validate", "other"]
TaskStatus = Literal["pending", "in_progress", "done"]


class Task(BaseModel):
    id: str
    type: TaskType
    title: str
    description: str = ""
    query: str = ""
    status: TaskStatus = "pending"


class TaskPlan(BaseModel):
    tasks: list[Task] = Field(default_factory=list)
