"""Build Citation list from retrieved papers referenced in outline / critiques."""

from __future__ import annotations

from athena.agents.critic import supported_only
from athena.schemas.citation import Citation
from athena.schemas.critique import Critique
from athena.schemas.knowledge_card import KnowledgeCard
from athena.schemas.outline import Outline


def collect_paper_ids(
    papers: list[KnowledgeCard],
    critiques: list[Critique],
    outline: Outline | None,
) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    valid = {p.paper_id for p in papers}

    def add(pid: str) -> None:
        if pid in valid and pid not in seen:
            seen.add(pid)
            ids.append(pid)

    for c in supported_only(critiques):
        for pid in c.evidence_paper_ids:
            add(pid)
    if outline:
        for section in outline.sections:
            for pid in section.evidence_paper_ids:
                add(pid)
    if not ids:
        for p in papers[:5]:
            add(p.paper_id)
    return ids


def cards_to_citations(papers: list[KnowledgeCard], paper_ids: list[str]) -> list[Citation]:
    by_id = {p.paper_id: p for p in papers}
    citations: list[Citation] = []
    for pid in paper_ids:
        card = by_id.get(pid)
        if not card:
            continue
        if not card.doi.strip() and not card.title.strip():
            continue
        citations.append(
            Citation(
                title=card.title,
                authors=card.authors,
                year=card.year,
                doi=card.doi,
                venue=card.venue,
            )
        )
    return citations


def build_citations_for_validation(
    papers: list[KnowledgeCard],
    critiques: list[Critique],
    outline: Outline | None,
) -> list[Citation]:
    ids = collect_paper_ids(papers, critiques, outline)
    return cards_to_citations(papers, ids)
