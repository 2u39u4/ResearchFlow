"""Writer Agent — outline scaffolding only (no full manuscript prose)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from athena.agents.critic import supported_only
from athena.config import Settings, get_settings
from athena.llm.client import LLMClient
from athena.schemas.critique import Critique
from athena.schemas.knowledge_card import KnowledgeCard
from athena.schemas.outline import DEFAULT_TODO_MARKER, Outline, OutlineSection

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = f"""You are an academic writing assistant producing ONLY an outline scaffold.
Output JSON:
{{"title": "...", "sections": [{{"heading": "...", "bullets": ["..."], "evidence_paper_ids": ["id"]}}]}}

Rules:
1. Do NOT write full paragraph prose or a submittable paper.
2. Each section's bullets must be short points; include at least one bullet with exactly: {DEFAULT_TODO_MARKER}
3. evidence_paper_ids must come from the provided paper list only.
4. Use supported critiques as hints for Related Work / Gap sections.
5. Typical sections: Introduction, Related Work, Gap Analysis, Method Sketch, Experiments Plan, Conclusion.
6. Do not invent paper_ids or citations."""


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


def fallback_outline(topic: str, critiques: list[Critique], papers: list[KnowledgeCard]) -> Outline:
    """Minimal outline when LLM fails."""
    evidence = [p.paper_id for p in papers[:3]]
    bullets = [
        f"Scope: {topic}",
        DEFAULT_TODO_MARKER,
    ]
    for c in supported_only(critiques)[:3]:
        bullets.append(f"[{c.type}] {c.claim[:120]}")
    return Outline(
        title=f"Research Outline: {topic}",
        sections=[
            OutlineSection(
                heading="Introduction",
                bullets=bullets,
                evidence_paper_ids=evidence,
            ),
            OutlineSection(
                heading="Related Work & Gaps",
                bullets=[DEFAULT_TODO_MARKER, "Summarize retrieved corpus."],
                evidence_paper_ids=evidence,
            ),
        ],
    )


def _critiques_for_prompt(critiques: list[Critique]) -> str:
    rows = [
        {
            "type": c.type,
            "claim": c.claim,
            "evidence_paper_ids": c.evidence_paper_ids,
            "confidence": c.confidence,
        }
        for c in supported_only(critiques)
    ]
    return json.dumps(rows, ensure_ascii=False, indent=2)


def _papers_for_prompt(papers: list[KnowledgeCard]) -> str:
    rows = [
        {"paper_id": p.paper_id, "title": p.title, "year": p.year, "venue": p.venue}
        for p in papers[:20]
    ]
    return json.dumps(rows, ensure_ascii=False, indent=2)


@dataclass
class WriterResult:
    topic: str
    outline: Outline
    model: str
    used_fallback: bool
    errors: list[str]


def run_writer(
    topic: str,
    papers: list[KnowledgeCard],
    critiques: list[Critique],
    *,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
) -> WriterResult:
    settings = settings or get_settings()
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must be non-empty")
    if not papers:
        raise ValueError("papers must be non-empty")

    model = settings.writer_llm_model or settings.default_llm_model
    if llm is None:
        llm = LLMClient(settings)

    user = (
        f"Topic: {topic}\n\n"
        f"Supported critiques:\n{_critiques_for_prompt(critiques)}\n\n"
        f"Papers:\n{_papers_for_prompt(papers)}"
    )

    try:
        text = llm.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            model=model,
            temperature=settings.writer_temperature,
            max_tokens=settings.writer_max_tokens,
        )
        data = _parse_llm_json(text)
        outline = Outline.model_validate(data)
        _ensure_todo_markers(outline)
        return WriterResult(
            topic=topic,
            outline=outline,
            model=model,
            used_fallback=False,
            errors=[],
        )
    except Exception as exc:
        logger.warning("writer fallback: %s", exc)
        outline = fallback_outline(topic, critiques, papers)
        return WriterResult(
            topic=topic,
            outline=outline,
            model=model,
            used_fallback=True,
            errors=[str(exc)],
        )


def _ensure_todo_markers(outline: Outline) -> None:
    has_todo = any(
        DEFAULT_TODO_MARKER in bullet for section in outline.sections for bullet in section.bullets
    )
    if not has_todo and outline.sections:
        outline.sections[0].bullets.append(DEFAULT_TODO_MARKER)
