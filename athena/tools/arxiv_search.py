"""arXiv search with rate limiting, disk cache, and backoff retries."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

import arxiv
import diskcache

from athena.config import get_settings

logger = logging.getLogger(__name__)

_last_request_at: float = 0.0
_MAX_RETRIES = 3
_ARXIV_CACHE: diskcache.Cache | None = None
_CACHE_TTL_SEC = 86400


def _arxiv_cache() -> diskcache.Cache:
    global _ARXIV_CACHE
    if _ARXIV_CACHE is None:
        settings = get_settings()
        settings.ensure_dirs()
        _ARXIV_CACHE = diskcache.Cache(str(settings.athena_cache_dir / "arxiv"))
    return _ARXIV_CACHE


def _cache_key(query: str, max_results: int) -> str:
    raw = json.dumps({"query": query, "max_results": max_results}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


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
    key = _cache_key(query, max_results)
    cached = _arxiv_cache().get(key)
    if cached is not None:
        logger.info("arxiv cache hit query=%r max_results=%d", query[:80], max_results)
        return [ArxivPaper(**item) for item in cached]

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            _throttle()
            # Match page_size to max_results — default Client(page_size=100) over-fetches and triggers 429.
            page_size = max(1, min(max_results, 50))
            settings = get_settings()
            delay = max(3.0, settings.arxiv_min_interval_sec)
            # Library default num_retries=3 multiplies 429 pressure; keep a single client retry.
            client = arxiv.Client(page_size=page_size, delay_seconds=delay, num_retries=1)
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
            _arxiv_cache().set(key, [p.to_dict() for p in papers], expire=_CACHE_TTL_SEC)
            return papers
        except Exception as exc:
            last_error = exc
            if "429" in str(exc):
                wait = min(180.0, 60.0 * (attempt + 1))
                logger.warning("arxiv 429 query=%r — sleeping %.0fs before retry", query[:60], wait)
                time.sleep(wait)
            else:
                time.sleep(2**attempt)
    if last_error:
        raise last_error
    return []
