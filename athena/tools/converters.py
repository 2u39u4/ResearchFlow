"""Convert API payloads to KnowledgeCard (metadata from API fields only)."""

from __future__ import annotations

from typing import Any

from athena.schemas.knowledge_card import KnowledgeCard
from athena.tools.arxiv_search import ArxivPaper
from athena.tools.normalize import normalize_doi


def _year_from_iso(date_str: str) -> int | None:
    if not date_str or len(date_str) < 4:
        return None
    try:
        return int(date_str[:4])
    except ValueError:
        return None


def arxiv_to_card(paper: ArxivPaper) -> KnowledgeCard:
    return KnowledgeCard(
        paper_id=f"arxiv:{paper.arxiv_id}",
        title=paper.title.strip(),
        authors=list(paper.authors),
        year=_year_from_iso(paper.published),
        venue="arXiv",
        doi="",
        url=paper.pdf_url or f"https://arxiv.org/abs/{paper.arxiv_id}",
        abstract=(paper.summary or "").strip(),
        source="arxiv",
    )


def semantic_scholar_to_card(item: dict[str, Any]) -> KnowledgeCard | None:
    title = (item.get("title") or "").strip()
    if not title:
        return None

    authors = [a.get("name", "") for a in (item.get("authors") or []) if a.get("name")]
    ext = item.get("externalIds") or {}
    doi = normalize_doi(ext.get("DOI"))
    arxiv_id = (ext.get("ArXiv") or "").strip()
    s2_id = item.get("paperId") or ""

    if doi:
        paper_id = f"doi:{doi}"
    elif arxiv_id:
        paper_id = f"arxiv:{arxiv_id}"
    elif s2_id:
        paper_id = f"s2:{s2_id}"
    else:
        paper_id = f"title:{title[:80]}"

    url = f"https://www.semanticscholar.org/paper/{s2_id}" if s2_id else ""

    return KnowledgeCard(
        paper_id=paper_id,
        title=title,
        authors=authors,
        year=item.get("year"),
        venue=(item.get("venue") or "").strip(),
        doi=doi,
        url=url,
        abstract=(item.get("abstract") or "").strip(),
        source="semantic_scholar",
    )


def crossref_work_to_card(work: dict[str, Any]) -> KnowledgeCard | None:
    title_list = work.get("title") or []
    title = (title_list[0] if title_list else "").strip()
    if not title:
        return None

    doi = normalize_doi(work.get("DOI"))
    paper_id = f"doi:{doi}" if doi else f"crossref:{work.get('URL', title[:40])}"

    authors = []
    for person in work.get("author") or []:
        given = person.get("given") or ""
        family = person.get("family") or ""
        name = f"{given} {family}".strip()
        if name:
            authors.append(name)

    issued = work.get("issued") or {}
    date_parts = issued.get("date-parts") or [[]]
    year = None
    if date_parts and date_parts[0]:
        try:
            year = int(date_parts[0][0])
        except (TypeError, ValueError, IndexError):
            year = None

    venue_list = work.get("container-title") or work.get("short-container-title") or []
    venue = (venue_list[0] if venue_list else "").strip()

    url = (work.get("URL") or "").strip()
    if not url and doi:
        url = f"https://doi.org/{doi}"

    abstract = (work.get("abstract") or "").strip()

    return KnowledgeCard(
        paper_id=paper_id,
        title=title,
        authors=authors,
        year=year,
        venue=venue,
        doi=doi,
        url=url,
        abstract=abstract,
        source="crossref",
    )
