"""arXiv search with rate limiting and exponential backoff retries."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import arxiv

from athena.config import get_settings

_last_request_at: float = 0.0
_MAX_RETRIES = 3


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    published: str
    summary: str
    pdf_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "authors": self.authors,
            "published": self.published,
            "summary": self.summary,
            "pdf_url": self.pdf_url,
        }


def _throttle() -> None:
    global _last_request_at
    settings = get_settings()
    interval = settings.arxiv_min_interval_sec
    elapsed = time.monotonic() - _last_request_at
    if elapsed < interval:
        time.sleep(interval - elapsed)
    _last_request_at = time.monotonic()


def search_arxiv(query: str, *, max_results: int = 5) -> list[ArxivPaper]:
    """Search arXiv and return structured paper metadata."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            _throttle()
            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            papers: list[ArxivPaper] = []
            for result in client.results(search):
                arxiv_id = result.entry_id.split("/")[-1]
                papers.append(
                    ArxivPaper(
                        arxiv_id=arxiv_id,
                        title=result.title,
                        authors=[a.name for a in result.authors],
                        published=result.published.isoformat() if result.published else "",
                        summary=(result.summary or "")[:2000],
                        pdf_url=result.pdf_url or "",
                    )
                )
            return papers
        except Exception as exc:
            last_error = exc
            time.sleep(2**attempt)
    if last_error:
        raise last_error
    return []
