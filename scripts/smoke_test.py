#!/usr/bin/env python3
"""W1 smoke test: SQLite + arXiv + optional LLM + optional Semantic Scholar."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from athena.config import get_settings
from athena.llm.client import LLMClient
from athena.storage.cache import clear_llm_cache, get_llm_cache, make_cache_key
from athena.storage.sqlite import get_db, init_db, insert_sample_records
from athena.tools.arxiv_search import search_arxiv
from athena.tools.semantic_scholar import ping as s2_ping


def step_db() -> None:
    print("\n[1/4] SQLite …")
    init_db()
    info = insert_sample_records()
    with get_db() as conn:
        paper_count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        trace_count = conn.execute("SELECT COUNT(*) FROM trace").fetchone()[0]
    print(f"  OK — papers={paper_count}, trace={trace_count}, run_id={info['run_id']}")


def step_arxiv() -> None:
    print("\n[2/4] arXiv search …")
    papers = search_arxiv("retrieval augmented generation", max_results=3)
    for i, p in enumerate(papers, 1):
        print(f"  {i}. {p.arxiv_id} — {p.title[:70]}…")
    if not papers:
        raise RuntimeError("arXiv returned no results")


def step_semantic_scholar() -> None:
    print("\n[3/4] Semantic Scholar (anonymous if no API key) …")
    settings = get_settings()
    if settings.semantic_scholar_uses_anonymous:
        print("  mode: anonymous (~1 req/s, may 429 if rate-limited)")
    else:
        print("  mode: API key")
    try:
        result = s2_ping()
        title = result.get("sample_title") or "n/a"
        print(f"  OK — sample: {str(title)[:70]}")
    except Exception as exc:
        print(f"  SKIP — {exc}")
        print("  (S2 optional for W1; retry after SEMANTIC_SCHOLAR_API_KEY is set)")


def step_llm() -> None:
    print("\n[4/4] LLM (OpenAI) …")
    settings = get_settings()
    if not settings.openai_api_key:
        print("  SKIP — OPENAI_API_KEY not set (copy .env.example → .env)")
        return

    client = LLMClient()
    messages = [{"role": "user", "content": "Reply with exactly: ATHENA_OK"}]
    r1 = client.chat(messages, max_tokens=16)
    print(f"  first call: {r1.strip()!r}")

    # cache hit — should not call API again for identical request
    cache_key = make_cache_key(
        messages,
        settings.default_llm_model,
        temperature=0.2,
        max_tokens=16,
        provider=settings.default_llm_provider,
    )
    assert get_llm_cache().get(cache_key) is not None
    r2 = client.chat(messages, max_tokens=16)
    print(f"  cached call: {r2.strip()!r}")
    print("  OK — diskcache hit verified")


def main() -> int:
    print("Athena W1 smoke test")
    settings = get_settings()
    settings.ensure_dirs()
    print(f"  data_dir={settings.athena_data_dir}")
    print(f"  db={settings.athena_db_path}")

    try:
        step_db()
        step_arxiv()
        step_semantic_scholar()
        step_llm()
    except Exception as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1

    print("\nAll required steps passed.")
    print("(LLM step is optional without OPENAI_API_KEY)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
