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


MAX_PLAN_QUERIES = 3


def _dispatch_fetch(name: str, query: str, limit: int) -> list[KnowledgeCard]:
    if name == "arxiv":
        return _fetch_arxiv(query, limit)
    if name == "semantic_scholar":
        return _fetch_semantic_scholar(query, limit)
    if name == "crossref":
        return _fetch_crossref(query, limit)
    raise ValueError(f"unknown source: {name}")


def _apply_year_filter(
    cards: list[KnowledgeCard],
    year_min: int | None,
    year_max: int | None,
) -> list[KnowledgeCard]:
    """Keep cards within [year_min, year_max]. Cards with unknown year are kept."""
    if year_min is None and year_max is None:
        return cards
    kept: list[KnowledgeCard] = []
    for c in cards:
        if c.year is None:
            kept.append(c)
            continue
        if year_min is not None and c.year < year_min:
            continue
        if year_max is not None and c.year > year_max:
            continue
        kept.append(c)
    return kept


def run_research(
    topic: str,
    *,
    arxiv_query: str | None = None,
    fallback_topic: str | None = None,
    per_source_limit: int = 15,
    min_cards: int = 10,
    extra_queries: list[str] | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
) -> ResearchResult:
    """
    Search arXiv, Semantic Scholar, and Crossref; deduplicate; return cards.

    When the planner supplies multiple search tasks, pass their queries via
    ``extra_queries`` — each source is queried with every plan query and the results
    merged, so the task plan materially drives retrieval. ``year_min`` / ``year_max``
    apply the planner's / UI's date constraints. Partial source failures are recorded
    in ``errors`` but do not abort the run.
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must be non-empty")

    # Plan-driven query set: primary topic + distinct extra queries (cost-capped).
    queries: list[str] = [topic]
    for q in extra_queries or []:
        q = (q or "").strip()
        if q and q not in queries:
            queries.append(q)
    queries = queries[:MAX_PLAN_QUERIES]

    raw: list[KnowledgeCard] = []
    errors: list[str] = []
    sources_ok: dict[str, bool] = {}

    arxiv_q = (arxiv_query or topic).strip()

    active_sources = ["arxiv", "crossref"]
    if not get_settings().semantic_scholar_uses_anonymous:
        active_sources.insert(1, "semantic_scholar")
    else:
        sources_ok["semantic_scholar"] = False
        errors.append("semantic_scholar skipped: no SEMANTIC_SCHOLAR_API_KEY")

    fb = (fallback_topic or "").strip()
    arxiv_fallback = bool(fb and fb != arxiv_q)

    for name in active_sources:
        got_any = False
        last_error: Exception | None = None
        for qi, q in enumerate(queries):
            source_query = arxiv_q if (name == "arxiv" and qi == 0) else q
            try:
                cards = _dispatch_fetch(name, source_query, per_source_limit)
                raw.extend(cards)
                got_any = True
                logger.info("%s returned %d cards for query=%r", name, len(cards), source_query)
            except Exception as exc:
                if name == "arxiv" and qi == 0 and arxiv_fallback and "429" not in str(exc):
                    try:
                        cards = _fetch_arxiv(fb, per_source_limit)
                        raw.extend(cards)
                        got_any = True
                        logger.info(
                            "arxiv returned %d cards after fallback query=%r", len(cards), fb
                        )
                        continue
                    except Exception as exc2:
                        exc = exc2
                last_error = exc
                logger.warning("%s failed for query=%r: %s", name, source_query, exc)
        sources_ok[name] = got_any
        if not got_any and last_error is not None:
            errors.append(f"{name} failed: {last_error}")

    required = _critical_source_names()
    if not any(sources_ok.get(name) for name in required):
        errors.insert(0, _critical_sources_message())

    merged = deduplicate_cards(raw)
    merged = _apply_year_filter(merged, year_min, year_max)
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
