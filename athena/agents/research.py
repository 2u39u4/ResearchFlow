"""Research Agent — multi-source retrieval, dedup, KnowledgeCard output."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

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


@dataclass
class ResearchResult:
    topic: str
    cards: list[KnowledgeCard]
    errors: list[str]

    def to_json(self, *, indent: int = 2) -> str:
        payload = {
            "topic": self.topic,
            "count": len(self.cards),
            "errors": self.errors,
            "cards": [c.model_dump() for c in self.cards],
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

    for name, fetcher in (
        ("arxiv", lambda: _fetch_arxiv(topic, per_source_limit)),
        ("semantic_scholar", lambda: _fetch_semantic_scholar(topic, per_source_limit)),
        ("crossref", lambda: _fetch_crossref(topic, per_source_limit)),
    ):
        try:
            cards = fetcher()
            raw.extend(cards)
            logger.info("%s returned %d cards for topic=%r", name, len(cards), topic)
        except Exception as exc:
            msg = f"{name} failed: {exc}"
            logger.warning(msg)
            errors.append(msg)

    merged = deduplicate_cards(raw)
    merged.sort(key=lambda c: (c.year or 0), reverse=True)

    if len(merged) < min_cards and not errors:
        errors.append(
            f"only {len(merged)} unique cards after dedup (target>={min_cards}); "
            "try a broader topic or increase per_source_limit"
        )

    return ResearchResult(topic=topic, cards=merged, errors=errors)
