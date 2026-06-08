"""Shared helpers for RQ evaluation experiments."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from athena.agents.research import run_research
from athena.schemas.critique import Critique
from athena.schemas.knowledge_card import KnowledgeCard
from athena.schemas.outline import Outline

EVAL_ROOT = Path(__file__).resolve().parents[1]
TOPICS_PATH = EVAL_ROOT / "topics" / "topic_set.json"
POOLS_DIR = EVAL_ROOT / "topics" / "pools"
RESULTS_ROOT = Path("results/experiments")
PROTOCOL_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_topic_set() -> dict[str, Any]:
    with TOPICS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def list_topics(*, limit: int | None = None, pools_only: bool = False) -> list[dict[str, Any]]:
    topics = load_topic_set()["topics"]
    if pools_only:
        topics = [t for t in topics if pool_has_arxiv(t["id"])]
    if limit is not None:
        return topics[:limit]
    return topics


def pool_path(topic_id: str) -> Path:
    return POOLS_DIR / f"{topic_id}.json"


def pool_has_arxiv(topic_id: str) -> bool:
    """True if an on-disk pool exists and arXiv succeeded when it was built."""
    path = pool_path(topic_id)
    if not path.is_file():
        return False
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        ok = data.get("sources_ok") or {}
        return bool(ok.get("arxiv")) and len(data.get("paper_ids") or []) > 0
    except (json.JSONDecodeError, OSError):
        return False


def load_reference_pool(topic_id: str) -> dict[str, Any]:
    path = pool_path(topic_id)
    if not path.is_file():
        raise FileNotFoundError(
            f"Reference pool missing for {topic_id}. Run: python scripts/run_experiments.py build-pools"
        )
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_reference_pool(
    topic_id: str,
    topic: str,
    domain: str,
    *,
    per_source_limit: int = 10,
    min_cards: int = 8,
) -> dict[str, Any]:
    """Run fixed-protocol retrieval and persist pool JSON."""
    result = run_research(
        topic,
        arxiv_query=topic,
        per_source_limit=per_source_limit,
        min_cards=min_cards,
    )
    if not result.critical_sources_ok:
        raise RuntimeError(f"Research failed for {topic_id}: {result.errors}")

    POOLS_DIR.mkdir(parents=True, exist_ok=True)
    cards = result.cards
    payload = {
        "topic_id": topic_id,
        "topic": topic,
        "domain": domain,
        "protocol_version": PROTOCOL_VERSION,
        "built_at": utc_now(),
        "per_source_limit": per_source_limit,
        "min_cards": min_cards,
        "research_errors": result.errors,
        "sources_ok": result.sources_ok,
        "pool_mode": "arxiv_crossref",
        "paper_ids": [c.paper_id for c in cards],
        "cards": [c.model_dump() for c in cards],
    }
    path = pool_path(topic_id)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def coerce_cards(raw: list) -> list[KnowledgeCard]:
    out: list[KnowledgeCard] = []
    for item in raw:
        if isinstance(item, KnowledgeCard):
            out.append(item)
        else:
            out.append(KnowledgeCard.model_validate(item))
    return out


def collect_output_paper_ids(
    *,
    critiques: list[Critique] | None = None,
    outline: Outline | None = None,
    extra_ids: list[str] | None = None,
) -> set[str]:
    ids: set[str] = set(extra_ids or [])
    for c in critiques or []:
        if isinstance(c, dict):
            ids.update(c.get("evidence_paper_ids") or [])
        else:
            ids.update(c.evidence_paper_ids)
    if outline:
        sections = outline.sections if hasattr(outline, "sections") else (outline.get("sections") or [])
        for section in sections:
            if isinstance(section, dict):
                ids.update(section.get("evidence_paper_ids") or [])
            else:
                ids.update(section.evidence_paper_ids)
    return ids


def coverage_rate(output_ids: set[str], pool_ids: set[str]) -> float:
    if not pool_ids:
        return 0.0
    return len(output_ids & pool_ids) / len(pool_ids)


def fake_citation_rate(validation_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Compute rates from validation_report dict rows."""
    total = len(validation_rows)
    if total == 0:
        return {"total": 0, "fake_rate": 0.0, "mismatch_rate": 0.0, "verified_rate": 0.0}
    n_nf = sum(1 for r in validation_rows if r.get("status") == "not_found")
    n_mm = sum(1 for r in validation_rows if r.get("status") == "mismatch")
    n_ok = sum(1 for r in validation_rows if r.get("status") == "verified")
    return {
        "total": total,
        "fake_rate": n_nf / total,
        "mismatch_rate": n_mm / total,
        "verified_rate": n_ok / total,
    }


def fake_rate_with_validator_filter(validation_rows: list[dict[str, Any]]) -> dict[str, float]:
    """Compare publish-all vs verified-only citation policies."""
    raw = fake_citation_rate(validation_rows)
    verified_only = [r for r in validation_rows if r.get("status") == "verified"]
    filtered = fake_citation_rate(verified_only)
    return {
        "without_validation": raw,
        "with_validation_verified_only": filtered,
        "blocked_count": raw["total"] - len(verified_only),
    }


def ensure_results_dir(rq: str) -> Path:
    path = RESULTS_ROOT / rq
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_run_result(rq: str, name: str, payload: dict[str, Any]) -> Path:
    out_dir = ensure_results_dir(rq)
    path = out_dir / f"{name}.json"
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    latest = out_dir / "latest.json"
    latest.write_text(text, encoding="utf-8")
    checkpoint = out_dir / "checkpoint.json"
    checkpoint.write_text(text, encoding="utf-8")
    return path


def checkpoint_path(rq: str) -> Path:
    return ensure_results_dir(rq) / "checkpoint.json"


def topic_rows_path(rq: str, topic_id: str) -> Path:
    return ensure_results_dir(rq) / "by_topic" / f"{topic_id}.json"


def row_key(row: dict[str, Any]) -> tuple[str, int]:
    return (str(row["topic_id"]), int(row["repeat"]))


def topic_repeats_done(rows: list[dict[str, Any]], topic_id: str, repeats: int) -> set[int]:
    return {int(r["repeat"]) for r in rows if r.get("topic_id") == topic_id}


def topic_is_complete(rows: list[dict[str, Any]], topic_id: str, repeats: int) -> bool:
    return topic_repeats_done(rows, topic_id, repeats) >= set(range(repeats))


def upsert_row(rows: list[dict[str, Any]], row: dict[str, Any]) -> list[dict[str, Any]]:
    key = row_key(row)
    kept = [r for r in rows if row_key(r) != key]
    kept.append(row)
    kept.sort(key=lambda r: (r.get("topic_id", ""), int(r.get("repeat", 0))))
    return kept


def load_run_checkpoint(rq: str) -> dict[str, Any] | None:
    path = checkpoint_path(rq)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_rows_from_by_topic(rq: str) -> list[dict[str, Any]]:
    root = ensure_results_dir(rq) / "by_topic"
    if not root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("t*.json")):
        with path.open(encoding="utf-8") as f:
            chunk = json.load(f)
        if isinstance(chunk, list):
            rows.extend(chunk)
    rows.sort(key=lambda r: (r.get("topic_id", ""), int(r.get("repeat", 0))))
    return rows


def resume_rows(
    rq: str,
    *,
    repeats: int,
    skip_judge: bool,
    fresh: bool = False,
) -> tuple[list[dict[str, Any]], str | None]:
    """Load prior rows for resume; returns (rows, created_at or None)."""
    if fresh:
        return [], None
    ckpt = load_run_checkpoint(rq)
    if ckpt:
        if ckpt.get("repeats") != repeats or ckpt.get("skip_judge") != skip_judge:
            raise RuntimeError(
                f"Checkpoint for {rq} has repeats={ckpt.get('repeats')} skip_judge={ckpt.get('skip_judge')}; "
                f"requested repeats={repeats} skip_judge={skip_judge}. Pass --fresh to start over."
            )
        return list(ckpt.get("rows") or []), ckpt.get("created_at")
    rows = load_rows_from_by_topic(rq)
    if rows:
        return rows, None
    return [], None


def save_topic_checkpoint(rq: str, payload: dict[str, Any], topic_id: str) -> None:
    """Flush after each topic: per-topic file + checkpoint + latest."""
    topic_rows = [r for r in payload.get("rows") or [] if r.get("topic_id") == topic_id]
    topic_rows_path(rq, topic_id).parent.mkdir(parents=True, exist_ok=True)
    topic_rows_path(rq, topic_id).write_text(
        json.dumps(topic_rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    checkpoint_path(rq).write_text(text, encoding="utf-8")
    (ensure_results_dir(rq) / "latest.json").write_text(text, encoding="utf-8")


def flush_run_checkpoint(rq: str, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    checkpoint_path(rq).write_text(text, encoding="utf-8")
    (ensure_results_dir(rq) / "latest.json").write_text(text, encoding="utf-8")


def seeded_rng(seed: int, *parts: str) -> random.Random:
    import hashlib

    payload = f"{seed}|" + "|".join(parts)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    return random.Random(int(digest[:16], 16))
