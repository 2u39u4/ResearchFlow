"""Disk-backed cache for LLM responses."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import diskcache

from athena.config import get_settings

_LLM_CACHE: diskcache.Cache | None = None


def get_llm_cache() -> diskcache.Cache:
    global _LLM_CACHE
    if _LLM_CACHE is None:
        settings = get_settings()
        settings.ensure_dirs()
        path = settings.athena_cache_dir / "llm"
        _LLM_CACHE = diskcache.Cache(str(path))
    return _LLM_CACHE


def make_cache_key(
    messages: list[dict[str, str]],
    model: str,
    **kwargs: Any,
) -> str:
    payload = {"messages": messages, "model": model, **kwargs}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def clear_llm_cache() -> int:
    """Remove all LLM cache entries. Returns number of keys cleared."""
    cache = get_llm_cache()
    count = len(cache)
    cache.clear()
    return count
