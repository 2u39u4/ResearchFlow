"""Merge duplicate papers across retrieval sources."""

from __future__ import annotations

from athena.schemas.knowledge_card import KnowledgeCard
from athena.tools.normalize import dedup_key


def deduplicate_cards(cards: list[KnowledgeCard]) -> list[KnowledgeCard]:
    """
    Keep one card per DOI or normalized title.
    Prefer the record with richer metadata; tie-break by source priority.
    """
    source_rank = {"crossref": 3, "semantic_scholar": 2, "arxiv": 1}
    best: dict[str, KnowledgeCard] = {}

    for card in cards:
        key = dedup_key(card.doi, card.title)
        if not key:
            continue
        existing = best.get(key)
        if existing is None:
            best[key] = card
            continue
        if card.metadata_richness() > existing.metadata_richness():
            best[key] = card
        elif card.metadata_richness() == existing.metadata_richness():
            if source_rank.get(card.source, 0) > source_rank.get(existing.source, 0):
                best[key] = card

    return list(best.values())
