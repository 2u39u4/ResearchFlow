"""LLM-as-judge: Depth scoring and pairwise preference for RQ evaluation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from athena.config import Settings, get_settings
from athena.llm.client import LLMClient
from eval.experiments.common import seeded_rng

logger = logging.getLogger(__name__)

Preference = Literal["A", "B", "tie"]


@dataclass
class DepthScore:
    score: int
    rationale: str
    raw: str


@dataclass
class PairwiseResult:
    winner: str  # label_a | label_b | tie
    rationale: str
    presentation: dict[str, str]  # blind A/B -> system label
    raw: str


def _parse_json_block(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def judge_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    return LLMClient(settings)


def judge_model(settings: Settings | None = None) -> tuple[str, str]:
    settings = settings or get_settings()
    model = settings.judge_llm_model or settings.default_llm_model
    provider = settings.judge_llm_provider or settings.default_llm_provider
    if model == (settings.default_llm_model) and provider == settings.default_llm_provider:
        logger.warning(
            "Judge uses same model/provider as subject system — set JUDGE_LLM_MODEL / JUDGE_LLM_PROVIDER "
            "to a different provider for bias control (see eval/judges/rubric.md)."
        )
    return model, provider


def score_depth(
    output_text: str,
    topic: str,
    *,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
) -> DepthScore:
    """Score analytical depth 1–5 using rubric.md."""
    settings = settings or get_settings()
    model, provider = judge_model(settings)
    llm = llm or judge_client(settings)

    system = (
        "You are an impartial academic evaluator. Score DEPTH from 1 to 5 using the rubric. "
        'Output JSON only: {"score": int, "rationale": "..."}'
    )
    user = f"Topic: {topic}\n\nOutput to evaluate:\n{output_text[:12000]}"

    text = llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model,
        provider=provider,
        temperature=0.1,
        max_tokens=512,
    )
    data = _parse_json_block(text)
    score = int(data.get("score", 0))
    score = max(1, min(5, score))
    return DepthScore(score=score, rationale=str(data.get("rationale", "")), raw=text)


def pairwise_preference(
    output_a: str,
    output_b: str,
    topic: str,
    *,
    label_a: str = "multi_agent",
    label_b: str = "single_agent",
    seed: int | None = None,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
) -> PairwiseResult:
    """Blind A/B comparison with randomized left-right order."""
    settings = settings or get_settings()
    seed = seed if seed is not None else settings.eval_random_seed
    rng = seeded_rng(seed, topic, label_a, label_b)
    swap = rng.random() < 0.5

    left_text, right_text = (output_b, output_a) if swap else (output_a, output_b)
    presentation = {"A": label_b if swap else label_a, "B": label_a if swap else label_b}

    model, provider = judge_model(settings)
    llm = llm or judge_client(settings)
    system = (
        "Blind comparison of two research-assistant outputs on the same topic and paper corpus. "
        "Pick which is better for literature-review planning (specific gaps, grounding, actionability). "
        'Output JSON only: {"preference": "A"|"B"|"tie", "rationale": "..."}'
    )
    user = f"Topic: {topic}\n\n--- Output A ---\n{left_text[:8000]}\n\n--- Output B ---\n{right_text[:8000]}"
    text = llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=model,
        provider=provider,
        temperature=0.1,
        max_tokens=512,
    )
    data = _parse_json_block(text)
    pref = str(data.get("preference", "tie")).upper()
    if pref not in ("A", "B"):
        winner = "tie"
    else:
        winner = presentation.get(pref, "tie")

    return PairwiseResult(
        winner=winner,
        rationale=str(data.get("rationale", "")),
        presentation=presentation,
        raw=text,
    )


def render_output_for_judge(
    *,
    topic: str,
    critiques: list | None = None,
    outline: dict | Any | None = None,
    extra_summary: str = "",
) -> str:
    """Plain-text bundle for judge prompts."""
    parts = [f"Topic: {topic}", extra_summary]
    if critiques:
        parts.append("Critiques:")
        for c in critiques:
            if hasattr(c, "model_dump"):
                c = c.model_dump()
            parts.append(
                f"- [{c.get('type')}] {c.get('claim')} | evidence={c.get('evidence_paper_ids')}"
            )
    if outline:
        if hasattr(outline, "model_dump"):
            outline = outline.model_dump()
        parts.append(f"Outline title: {outline.get('title')}")
        for sec in outline.get("sections") or []:
            parts.append(f"## {sec.get('heading')}")
            for b in sec.get("bullets") or []:
                parts.append(f"  - {b}")
            parts.append(f"  evidence: {sec.get('evidence_paper_ids')}")
    return "\n".join(parts)
