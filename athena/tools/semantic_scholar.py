"""Semantic Scholar API — works without API key (anonymous, ~1 req/s)."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import requests

from athena.config import get_settings

S2_BASE = "https://api.semanticscholar.org/graph/v1"
_last_request_at: float = 0.0
_MAX_RETRIES = 3


def _throttle() -> None:
    global _last_request_at
    settings = get_settings()
    # Anonymous tier is strict; use at least 1.5s when no API key.
    interval = settings.semantic_scholar_min_interval_sec
    if settings.semantic_scholar_uses_anonymous:
        interval = max(interval, 1.5)
    elapsed = time.monotonic() - _last_request_at
    if elapsed < interval:
        time.sleep(interval - elapsed)
    _last_request_at = time.monotonic()


def _headers() -> dict[str, str]:
    settings = get_settings()
    headers = {"Accept": "application/json"}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    return headers


def search_papers(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """
    Search papers via Semantic Scholar.
    Uses anonymous access when SEMANTIC_SCHOLAR_API_KEY is empty.
    Retries on 429 with exponential backoff.
    """
    url = f"{S2_BASE}/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,venue,externalIds,abstract",
    }
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        _throttle()
        resp = requests.get(url, params=params, headers=_headers(), timeout=30)
        if resp.status_code == 429:
            wait = 2 ** attempt
            time.sleep(wait)
            last_error = requests.HTTPError(
                f"429 Too Many Requests (retry {attempt + 1}/{_MAX_RETRIES})",
                response=resp,
            )
            continue
        resp.raise_for_status()
        data = resp.json()
        return data.get("data") or []
    if last_error:
        raise last_error
    return []


def lookup_by_doi(doi: str) -> dict[str, Any] | None:
    """Fetch paper metadata by DOI via Semantic Scholar."""
    from athena.tools.normalize import normalize_doi

    doi = normalize_doi(doi)
    if not doi:
        return None
    paper_id = quote(f"DOI:{doi}", safe="")
    _throttle()
    url = f"{S2_BASE}/paper/{paper_id}"
    params = {"fields": "title,authors,year,venue,externalIds,abstract,paperId"}
    resp = requests.get(url, params=params, headers=_headers(), timeout=30)
    if resp.status_code in (404, 429):
        return None
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, dict) and data.get("title") else None


def ping() -> dict[str, Any]:
    """Lightweight connectivity check (one search, one result)."""
    results = search_papers("transformer", limit=1)
    settings = get_settings()
    return {
        "ok": True,
        "anonymous": settings.semantic_scholar_uses_anonymous,
        "count": len(results),
        "sample_title": results[0].get("title") if results else None,
    }
