"""Critic Agent — gap / weakness / relative novelty with mandatory evidence."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from athena.config import Settings, get_settings
from athena.llm.client import LLMClient
from athena.schemas.critique import Critique, CritiqueBatch, CritiqueStatus
from athena.schemas.knowledge_card import KnowledgeCard

logger = logging.getLogger(__name__)

# Absolute novelty phrases — reject or mark unsupported (C6).
_ABSOLUTE_NOVELTY_RE = re.compile(
    r"|".join(
        [
            r"\bfirst\s+(ever|to)\b",
            r"\bnever\s+(been|before)\b",
            r"\bno\s+prior\s+work\b",
            r"\bstate\s+of\s+the\s+art\b",
            r"\bworld(?:'s|s)?\s+first\b",
            r"\bunprecedented\b",
            r"\bgroundbreaking\b",
        ]
    ),
    re.IGNORECASE,
)

_RELATIVE_NOVELTY_RE = re.compile(
    r"|".join(
        [
            r"\bamong\s+the\s+retrieved\b",
            r"\bin\s+the\s+\d+\s+retrieved\b",
            r"\bwithin\s+this\s+(corpus|set|literature\s+set)\b",
            r"\bnot\s+found\s+in\s+the\s+retrieved\b",
            r"\bnone\s+of\s+the\s+\d+\s+retrieved\b",
            r"\bbased\s+on\s+the\s+retrieved\s+\d+\s+papers\b",
            r"\bamong\s+these\s+\d+\s+papers\b",
        ]
    ),
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """You are an academic research critic. Analyze ONLY the papers provided.
Output valid JSON with this exact shape:
{"critiques": [{"claim": "...", "type": "gap|weakness|novelty", "evidence_paper_ids": ["id1"], "confidence": 0.0-1.0}]}

Rules:
1. Every critique MUST cite at least one paper_id from the provided list in evidence_paper_ids.
2. type=gap: research gaps or under-explored directions suggested by contrasts across papers.
3. type=weakness: methodological, experimental, evaluation, or reproducibility weaknesses in specific papers.
4. type=novelty: ONLY relative novelty — compare within the retrieved set. Start claims with phrasing like
   "Among the N retrieved papers, ..." or "In the retrieved literature set, no paper appears to ...".
   NEVER claim absolute first-ever novelty, "state of the art", "never been done", or similar.
5. Do not invent paper_ids, titles, authors, or findings not supported by the context.
6. Produce 3-8 diverse critiques when enough papers exist; fewer if the corpus is tiny.
7. confidence reflects how strongly the evidence in the cited papers supports the claim (0-1)."""


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


def papers_context(cards: list[KnowledgeCard], *, max_abstract_chars: int = 600) -> str:
    """Compact corpus description for the LLM prompt."""
    rows: list[dict] = []
    for c in cards:
        abstract = c.abstract or ""
        if len(abstract) > max_abstract_chars:
            abstract = abstract[: max_abstract_chars - 3] + "..."
        rows.append(
            {
                "paper_id": c.paper_id,
                "title": c.title,
                "year": c.year,
                "venue": c.venue,
                "authors": c.authors[:6],
                "abstract": abstract,
                "contributions": c.contributions,
                "methods": c.methods,
                "limitations": c.limitations,
            }
        )
    return json.dumps(rows, ensure_ascii=False, indent=2)


def bind_evidence(
    critiques: list[Critique],
    valid_paper_ids: set[str],
) -> list[Critique]:
    """Keep only evidence ids that exist; mark empty evidence as unsupported."""
    bound: list[Critique] = []
    for c in critiques:
        filtered = [pid for pid in c.evidence_paper_ids if pid in valid_paper_ids]
        if not filtered:
            bound.append(
                c.model_copy(
                    update={
                        "evidence_paper_ids": [],
                        "status": "unsupported",
                        "notes": (c.notes + "; " if c.notes else "")
                        + "no valid evidence_paper_ids in retrieved corpus",
                    }
                )
            )
            continue
        bound.append(
            c.model_copy(
                update={
                    "evidence_paper_ids": filtered,
                    "status": c.status if c.status == "unsupported" else "supported",
                }
            )
        )
    return bound


def check_relative_novelty(claim: str, *, n_papers: int) -> tuple[str, CritiqueStatus, str]:
    """
    Enforce relative novelty wording for type=novelty claims.
    Returns (possibly adjusted claim, status, notes).
    """
    if _ABSOLUTE_NOVELTY_RE.search(claim):
        return claim, "unsupported", "absolute novelty phrasing not allowed"

    if _RELATIVE_NOVELTY_RE.search(claim):
        return claim, "supported", ""

    prefix = f"Among the {n_papers} retrieved papers, "
    adjusted = prefix + claim[0].lower() + claim[1:] if claim else claim
    return adjusted, "supported", "prefixed relative novelty scope"


def apply_novelty_policy(critiques: list[Critique], *, n_papers: int) -> list[Critique]:
    out: list[Critique] = []
    for c in critiques:
        if c.type != "novelty":
            out.append(c)
            continue
        claim, status, note = check_relative_novelty(c.claim, n_papers=n_papers)
        notes = c.notes
        if note:
            notes = f"{notes}; {note}".strip("; ")
        if status == "unsupported":
            out.append(
                c.model_copy(
                    update={
                        "claim": claim,
                        "status": "unsupported",
                        "notes": notes or note,
                    }
                )
            )
        else:
            out.append(
                c.model_copy(
                    update={
                        "claim": claim,
                        "status": "supported" if c.status != "unsupported" else "unsupported",
                        "notes": notes,
                    }
                )
            )
    return out


def supported_only(critiques: list[Critique]) -> list[Critique]:
    return [c for c in critiques if c.status == "supported"]


def grounding_rate(critiques: list[Critique]) -> float:
    if not critiques:
        return 0.0
    supported = sum(1 for c in critiques if c.status == "supported" and c.evidence_paper_ids)
    return supported / len(critiques)


@dataclass
class CriticResult:
    topic: str
    corpus_size: int
    critiques: list[Critique]
    dropped_unsupported: int
    evidence_grounding_rate: float
    model: str
    errors: list[str]

    def to_json(self, *, indent: int = 2) -> str:
        payload = {
            "topic": self.topic,
            "corpus_size": self.corpus_size,
            "model": self.model,
            "evidence_grounding_rate": round(self.evidence_grounding_rate, 4),
            "dropped_unsupported": self.dropped_unsupported,
            "errors": self.errors,
            "critiques": [c.model_dump() for c in self.critiques],
            "supported_critiques": [c.model_dump() for c in supported_only(self.critiques)],
        }
        return json.dumps(payload, indent=indent, ensure_ascii=False)


def run_critic(
    topic: str,
    papers: list[KnowledgeCard],
    *,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    max_critiques: int | None = None,
) -> CriticResult:
    """
    Generate evidence-grounded critiques from retrieved KnowledgeCards.
    """
    settings = settings or get_settings()
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must be non-empty")
    if not papers:
        raise ValueError("papers must be non-empty for critic analysis")

    valid_ids = {p.paper_id for p in papers}
    n = len(papers)
    model = settings.critic_llm_model or settings.default_llm_model
    max_critiques = max_critiques or settings.critic_max_critiques
    errors: list[str] = []

    user_prompt = (
        f"Research topic: {topic}\n"
        f"Number of retrieved papers (N): {n}\n"
        f"Produce at most {max_critiques} critiques.\n\n"
        f"Papers JSON:\n{papers_context(papers)}"
    )

    raw_critiques: list[Critique] = []
    if llm is None:
        llm = LLMClient(settings)

    try:
        text = llm.chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=settings.critic_temperature,
            max_tokens=settings.critic_max_tokens,
        )
        data = _parse_llm_json(text)
        batch = CritiqueBatch.model_validate(data)
        raw_critiques = batch.critiques[:max_critiques]
    except Exception as exc:
        msg = f"llm_parse_failed: {exc}"
        logger.exception(msg)
        errors.append(msg)
        return CriticResult(
            topic=topic,
            corpus_size=n,
            critiques=[],
            dropped_unsupported=0,
            evidence_grounding_rate=0.0,
            model=model,
            errors=errors,
        )

    processed = apply_novelty_policy(raw_critiques, n_papers=n)
    processed = bind_evidence(processed, valid_ids)
    dropped = sum(1 for c in processed if c.status == "unsupported")

    return CriticResult(
        topic=topic,
        corpus_size=n,
        critiques=processed,
        dropped_unsupported=dropped,
        evidence_grounding_rate=grounding_rate(processed),
        model=model,
        errors=errors,
    )
