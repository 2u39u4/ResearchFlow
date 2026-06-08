#!/usr/bin/env python3
"""Smoke test: Gemini judge (depth + pairwise) for RQ evaluation setup."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from athena.config import get_settings
from eval.judges.llm_judge import judge_model, pairwise_preference, score_depth


def main() -> int:
    settings = get_settings()
    if not settings.gemini_api_key.strip():
        print("FAIL: GEMINI_API_KEY is empty — paste your key in .env and rerun.")
        return 1

    model, provider = judge_model(settings)
    print(f"Judge: provider={provider} model={model}")
    print(f"Subject: provider={settings.default_llm_provider} model={settings.default_llm_model}")

    topic = "retrieval augmented generation"
    sample = (
        "Critiques:\n"
        "- [gap] RAG systems often lack citation verification | evidence=['arxiv:2501.00001']\n"
        "Outline title: Survey of RAG\n"
        "## Verification\n  - Add DOI checks\n  evidence: ['arxiv:2501.00001']"
    )

    print("Calling score_depth...")
    depth = score_depth(sample, topic, settings=settings)
    print(f"  depth score={depth.score} rationale={depth.rationale[:120]}...")

    print("Calling pairwise_preference...")
    pw = pairwise_preference(
        sample + "\n(multi variant)",
        sample + "\n(single variant)",
        topic,
        settings=settings,
        seed=settings.eval_random_seed,
    )
    print(f"  winner={pw.winner} presentation={pw.presentation}")

    print("OK: Gemini judge smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
