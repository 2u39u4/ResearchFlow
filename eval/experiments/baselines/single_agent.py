"""Single-agent baseline: one LLM call over shared retrieved corpus (RQ1)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from athena.agents.critic import apply_novelty_policy, bind_evidence, papers_context
from athena.config import Settings, get_settings
from athena.llm.client import LLMClient
from athena.schemas.critique import Critique, CritiqueBatch
from athena.schemas.knowledge_card import KnowledgeCard
from athena.schemas.outline import Outline

logger = logging.getLogger(__name__)

_SYSTEM = """You are a single research assistant (no multi-agent pipeline).
Given retrieved papers, produce ONE JSON object:
{
  "critiques": [{"claim": "...", "type": "gap|weakness|novelty", "evidence_paper_ids": ["..."], "confidence": 0.0-1.0}],
  "outline": {
    "title": "...",
    "sections": [{"heading": "...", "bullets": ["..."], "evidence_paper_ids": ["..."]}]
  }
}
Rules: use only provided paper_ids; relative novelty only; 3-6 critiques; short outline bullets."""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


@dataclass
class SingleAgentResult:
    topic: str
    critiques: list[Critique]
    outline: Outline | None
    model: str
    errors: list[str]


def run_single_agent(
    topic: str,
    papers: list[KnowledgeCard],
    *,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
) -> SingleAgentResult:
    settings = settings or get_settings()
    model = settings.default_llm_model
    llm = llm or LLMClient(settings)
    valid_ids = {p.paper_id for p in papers}
    n = len(papers)
    errors: list[str] = []

    user = (
        f"Topic: {topic}\nN papers: {n}\n\n"
        f"Papers:\n{papers_context(papers)}\n\n"
        "Produce gaps, weaknesses, and a brief outline scaffold."
    )
    try:
        text = llm.chat(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": user}],
            model=model,
            temperature=settings.critic_temperature,
            max_tokens=settings.critic_max_tokens,
        )
        data = _parse_json(text)
        raw_critiques = CritiqueBatch.model_validate(
            {"critiques": data.get("critiques", [])}
        ).critiques
        processed = bind_evidence(apply_novelty_policy(raw_critiques, n_papers=n), valid_ids)
        outline = None
        if data.get("outline"):
            outline = Outline.model_validate(data["outline"])
        return SingleAgentResult(
            topic=topic, critiques=processed, outline=outline, model=model, errors=errors
        )
    except Exception as exc:
        logger.exception("single_agent failed")
        errors.append(str(exc))
        return SingleAgentResult(
            topic=topic, critiques=[], outline=None, model=model, errors=errors
        )
