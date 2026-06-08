"""Research Agent — multi-source retrieval, dedup, KnowledgeCard output."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from athena.config import get_settings
from athena.schemas.knowledge_card import KnowledgeCard
from athena.tools.arxiv_search import search_arxiv
from athena.tools.converters import (
    arxiv_to_card,
    crossref_work_to_card,
    semantic_scholar_to_card,
)
from athena.tools.crossref import search_by_title
from athena.tools.dedup import deduplicate_cards
from athena.tools.semantic_scholar import search_papers as search_semantic_scholar

logger = logging.getLogger(__name__)

CRITICAL_SOURCES = ("arxiv", "semantic_scholar")
CRITICAL_SOURCES_MSG = (
    "critical sources failed: both arXiv and Semantic Scholar failed "
    "(corpus may be Crossref-only and incomplete). "
    "Configure SEMANTIC_SCHOLAR_API_KEY, wait out rate limits, and retry."
)
CRITICAL_SOURCES_ANON_MSG = (
    "critical source failed: arXiv failed "
    "(Semantic Scholar skipped — no SEMANTIC_SCHOLAR_API_KEY). "
    "Wait out arXiv rate limits or retry with a shorter topic."
)


class CriticalResearchSourcesError(RuntimeError):
    """Raised when neither arXiv nor Semantic Scholar succeeded."""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__(self.errors[0] if self.errors else CRITICAL_SOURCES_MSG)


@dataclass
class ResearchResult:
    topic: str
    cards: list[KnowledgeCard]
    errors: list[str]
    sources_ok: dict[str, bool] = field(default_factory=dict)

    @property
    def critical_sources_ok(self) -> bool:
        required = _critical_source_names()
        return any(self.sources_ok.get(name, False) for name in required)

    def to_json(self, *, indent: int = 2) -> str:
        return _research_result_to_json(self, indent=indent)


def _critical_source_names() -> tuple[str, ...]:
    if get_settings().semantic_scholar_uses_anonymous:
        return ("arxiv",)
    return CRITICAL_SOURCES


def _critical_sources_message() -> str:
    if get_settings().semantic_scholar_uses_anonymous:
        return CRITICAL_SOURCES_ANON_MSG
    return CRITICAL_SOURCES_MSG


def _research_result_to_json(result: ResearchResult, *, indent: int = 2) -> str:
    payload = {
        "topic": result.topic,
        "count": len(result.cards),
        "errors": result.errors,
        "sources_ok": result.sources_ok,
        "critical_sources_ok": result.critical_sources_ok,
        "cards": [c.model_dump() for c in result.cards],
    }
    return json.dumps(payload, indent=indent, ensure_ascii=False)


def _fetch_arxiv(topic: str, limit: int) -> list[KnowledgeCard]:
    papers = search_arxiv(topic, max_results=limit)
    return [arxiv_to_card(p) for p in papers]


def _fetch_semantic_scholar(topic: str, limit: int) -> list[KnowledgeCard]:
    items = search_semantic_scholar(topic, limit=limit)
    cards: list[KnowledgeCard] = []
    for item in items:
        card = semantic_scholar_to_card(item)
        if card:
            cards.append(card)
    return cards


def _fetch_crossref(topic: str, limit: int) -> list[KnowledgeCard]:
    works = search_by_title(topic, rows=limit)
    cards: list[KnowledgeCard] = []
    for work in works:
        card = crossref_work_to_card(work)
        if card:
            cards.append(card)
    return cards


def run_research(
    topic: str,
    *,
    arxiv_query: str | None = None,
    fallback_topic: str | None = None,
    per_source_limit: int = 15,
    min_cards: int = 10,
) -> ResearchResult:
    """
    Search arXiv, Semantic Scholar, and Crossref; deduplicate; return cards.
    Partial source failures are recorded in errors but do not abort the run.
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must be non-empty")

    raw: list[KnowledgeCard] = []
    errors: list[str] = []
    sources_ok: dict[str, bool] = {}

    arxiv_q = (arxiv_query or topic).strip()

    sources = [
        ("arxiv", lambda: _fetch_arxiv(arxiv_q, per_source_limit)),
        ("crossref", lambda: _fetch_crossref(topic, per_source_limit)),
    ]
    if not get_settings().semantic_scholar_uses_anonymous:
        sources.insert(
            1,
            ("semantic_scholar", lambda: _fetch_semantic_scholar(topic, per_source_limit)),
        )
    elif get_settings().semantic_scholar_uses_anonymous:
        sources_ok["semantic_scholar"] = False
        errors.append("semantic_scholar skipped: no SEMANTIC_SCHOLAR_API_KEY")

    fb = (fallback_topic or "").strip()
    arxiv_fallback = bool(fb and fb != arxiv_q)

    for name, fetcher in sources:
        try:
            cards = fetcher()
            raw.extend(cards)
            sources_ok[name] = True
            logger.info("%s returned %d cards for topic=%r", name, len(cards), topic)
        except Exception as exc:
            if name == "arxiv" and arxiv_fallback and "429" not in str(exc):
                try:
                    cards = _fetch_arxiv(fb, per_source_limit)
                    raw.extend(cards)
                    sources_ok[name] = True
                    logger.info(
                        "%s returned %d cards after fallback query=%r",
                        name,
                        len(cards),
                        fb,
                    )
                    continue
                except Exception as exc2:
                    exc = exc2
            sources_ok[name] = False
            msg = f"{name} failed: {exc}"
            logger.warning(msg)
            errors.append(msg)

    required = _critical_source_names()
    if not any(sources_ok.get(name) for name in required):
        errors.insert(0, _critical_sources_message())

    merged = deduplicate_cards(raw)
    merged.sort(key=lambda c: c.year or 0, reverse=True)

    if len(merged) < min_cards and not errors:
        errors.append(
            f"only {len(merged)} unique cards after dedup (target>={min_cards}); "
            "try a broader topic or increase per_source_limit"
        )

    return ResearchResult(
        topic=topic,
        cards=merged,
        errors=errors,
        sources_ok=sources_ok,
    )
