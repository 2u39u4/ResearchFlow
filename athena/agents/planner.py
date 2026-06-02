"""Planner Agent — structured task plan with LLM + template fallback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from athena.config import Settings, get_settings
from athena.llm.client import LLMClient
from athena.schemas.task import Task, TaskPlan

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a research workflow planner. Output JSON only:
{"tasks": [{"id": "t1", "type": "search|analyze|outline|validate|other", "title": "...", "description": "...", "query": "optional search query"}]}

Rules:
- Produce 3-5 tasks covering literature search, gap/weakness analysis, outline scaffolding, and citation validation.
- type=search tasks must include a concrete query string.
- Keep ids short (t1, t2, ...).
- Do not include tasks that require fabricating paper metadata."""


def default_task_plan(topic: str) -> TaskPlan:
    """Fixed template when LLM output is unavailable."""
    return TaskPlan(
        tasks=[
            Task(
                id="t1",
                type="search",
                title="Literature retrieval",
                description="Retrieve papers from arXiv, Semantic Scholar, and Crossref.",
                query=topic,
            ),
            Task(
                id="t2",
                type="analyze",
                title="Gap and weakness analysis",
                description="Critique corpus for gaps, weaknesses, and relative novelty.",
            ),
            Task(
                id="t3",
                type="outline",
                title="Outline scaffolding",
                description="Build section outline with evidence placeholders and TODO markers.",
            ),
            Task(
                id="t4",
                type="validate",
                title="Citation validation",
                description="Verify bibliography entries against external APIs.",
            ),
        ]
    )


def _parse_llm_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


@dataclass
class PlannerResult:
    topic: str
    plan: TaskPlan
    model: str
    used_fallback: bool
    errors: list[str]


def run_planner(
    topic: str,
    *,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
) -> PlannerResult:
    settings = settings or get_settings()
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must be non-empty")

    model = settings.planner_llm_model or settings.default_llm_model
    if llm is None:
        llm = LLMClient(settings)

    try:
        text = llm.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Research topic: {topic}\nReturn a task plan JSON.",
                },
            ],
            model=model,
            temperature=settings.planner_temperature,
            max_tokens=settings.planner_max_tokens,
        )
        data = _parse_llm_json(text)
        plan = TaskPlan.model_validate(data)
        if not plan.tasks:
            raise ValueError("empty task list")
        for task in plan.tasks:
            if task.type == "search" and not task.query.strip():
                task.query = topic
        return PlannerResult(
            topic=topic,
            plan=plan,
            model=model,
            used_fallback=False,
            errors=[],
        )
    except Exception as exc:
        logger.warning("planner fallback: %s", exc)
        return PlannerResult(
            topic=topic,
            plan=default_task_plan(topic),
            model=model,
            used_fallback=True,
            errors=[str(exc)],
        )
