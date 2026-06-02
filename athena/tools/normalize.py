"""Normalize titles and DOIs for deduplication."""

from __future__ import annotations

import re
import unicodedata


def normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix) :]
    return d.strip()


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    t = unicodedata.normalize("NFKD", title)
    t = t.lower()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def dedup_key(doi: str, title: str) -> str:
    ndoi = normalize_doi(doi)
    if ndoi:
        return f"doi:{ndoi}"
    nt = normalize_title(title)
    return f"title:{nt}" if nt else ""
