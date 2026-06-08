"""Crossref REST API — polite pool via mailto in User-Agent."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import quote

import requests

from athena.config import get_settings

CROSSREF_BASE = "https://api.crossref.org"
_last_request_at: float = 0.0
_MAX_RETRIES = 6
_MIN_INTERVAL = 1.0


def _throttle() -> None:
    global _last_request_at
    elapsed = time.monotonic() - _last_request_at
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _last_request_at = time.monotonic()


def _headers() -> dict[str, str]:
    settings = get_settings()
    mailto = settings.crossref_mailto.strip() or "athena@example.com"
    return {
        "Accept": "application/json",
        "User-Agent": f"AthenaResearchFlow/0.1 (mailto:{mailto})",
    }


def _get_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{CROSSREF_BASE}{path}"
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        _throttle()
        try:
            resp = requests.get(
                url, params=params, headers=_headers(), timeout=60, proxies={"http": None, "https": None}
            )
        except requests.RequestException as exc:
            time.sleep(min(30, 2 ** (attempt + 1)))
            last_error = exc
            continue
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(2**attempt)
            last_error = requests.HTTPError(
                f"{resp.status_code} from Crossref (retry {attempt + 1}/{_MAX_RETRIES})",
                response=resp,
            )
            continue
        resp.raise_for_status()
        return resp.json()
    if last_error:
        raise last_error
    return {}


def lookup_doi(doi: str) -> dict[str, Any] | None:
    """Fetch a single work by DOI."""
    from athena.tools.normalize import normalize_doi

    doi = normalize_doi(doi.strip())
    if not doi:
        return None
    encoded = quote(doi, safe="")
    data = _get_json(f"/works/{encoded}")
    message = data.get("message")
    return message if isinstance(message, dict) else None


def search_by_title(title: str, *, rows: int = 5) -> list[dict[str, Any]]:
    """Search works by title (best-effort)."""
    data = _get_json(
        "/works",
        params={
            "query.title": title,
            "rows": rows,
            "select": "DOI,title,author,issued,container-title,URL,abstract",
        },
    )
    items = data.get("message", {}).get("items") or []
    return [i for i in items if isinstance(i, dict)]
