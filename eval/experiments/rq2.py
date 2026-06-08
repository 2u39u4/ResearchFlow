"""RQ2: Ablation — Research+Writer vs Research+Critic+Writer."""

from __future__ import annotations

import logging
from typing import Any

from athena.agents.critic import grounding_rate, run_critic, supported_only
from athena.agents.writer import run_writer
from athena.config import get_settings
from athena.graph.citations_from_corpus import build_citations_for_validation
from athena.tools.citation_validator import validate_citations

from eval.experiments.common import (
    coerce_cards,
    fake_citation_rate,
    list_topics,
    load_reference_pool,
    pool_has_arxiv,
    resume_rows,
    save_run_result,
    save_topic_checkpoint,
    topic_is_complete,
    topic_repeats_done,
    upsert_row,
    utc_now,
)
from eval.judges.llm_judge import render_output_for_judge, score_depth

logger = logging.getLogger(__name__)


def run_writer_only(topic: str, cards: list) -> dict[str, Any]:
    writer = run_writer(topic, cards, critiques=[])
    citations = build_citations_for_validation(cards, [], writer.outline)
    validation = validate_citations(citations)
    return {
        "outline": writer.outline.model_dump() if writer.outline else None,
        "writer_model": writer.model,
        "errors": writer.errors,
        "evidence_grounding_rate": 0.0,
        "critiques": [],
        "citations": [c.model_dump() for c in citations],
        "validation_report": [v.model_dump() for v in validation],
        "fake_citation_rate": fake_citation_rate([v.model_dump() for v in validation]),
    }


def run_with_critic(topic: str, cards: list) -> dict[str, Any]:
    critic = run_critic(topic, cards)
    writer = run_writer(topic, cards, critic.critiques)
    citations = build_citations_for_validation(cards, critic.critiques, writer.outline)
    validation = validate_citations(citations)
    supported = supported_only(critic.critiques)
    return {
        "outline": writer.outline.model_dump() if writer.outline else None,
        "critiques": [c.model_dump() for c in critic.critiques],
        "supported_critiques": len(supported),
        "evidence_grounding_rate": grounding_rate(critic.critiques),
        "citations": [c.model_dump() for c in citations],
        "validation_report": [v.model_dump() for v in validation],
        "fake_citation_rate": fake_citation_rate([v.model_dump() for v in validation]),
        "errors": critic.errors + writer.errors,
    }


def run_rq2(
    *,
    limit: int | None = 3,
    repeats: int | None = None,
    skip_judge: bool = False,
    topic_ids: list[str] | None = None,
    fresh: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    repeats = repeats if repeats is not None else settings.eval_default_repeats
    topics = list_topics(limit=limit)
    if topic_ids:
        topics = [t for t in topics if t["id"] in topic_ids]
    topics = [t for t in topics if pool_has_arxiv(t["id"])]
    if not topics:
        raise RuntimeError("No topics with arXiv reference pools — run build-pools first")

    rows, created_at = resume_rows("rq2", repeats=repeats, skip_judge=skip_judge, fresh=fresh)
    if created_at:
        logger.info("RQ2 resume: %d prior rows from checkpoint", len(rows))

    def _payload() -> dict[str, Any]:
        return {
            "rq": "RQ2",
            "description": "Ablation: Research+Writer vs Research+Critic+Writer",
            "repeats": repeats,
            "skip_judge": skip_judge,
            "created_at": created_at or utc_now(),
            "updated_at": utc_now(),
            "topic_count": len(topics),
            "rows": rows,
        }

    for spec in topics:
        tid = spec["id"]
        if topic_is_complete(rows, tid, repeats):
            logger.info("RQ2 skip %s — already complete (%d repeats)", tid, repeats)
            continue

        topic = spec["topic"]
        pool = load_reference_pool(tid)
        cards = coerce_cards(pool["cards"])
        done_reps = topic_repeats_done(rows, tid, repeats)

        for rep in range(repeats):
            if rep in done_reps:
                logger.info("RQ2 skip %s rep=%d — checkpoint hit", tid, rep)
                continue

            no_critic = run_writer_only(topic, cards)
            with_critic = run_with_critic(topic, cards)

            row: dict[str, Any] = {
                "topic_id": tid,
                "topic": topic,
                "repeat": rep,
                "no_critic": no_critic,
                "with_critic": with_critic,
                "delta_grounding": with_critic["evidence_grounding_rate"] - no_critic["evidence_grounding_rate"],
                "delta_fake_rate": (
                    no_critic["fake_citation_rate"]["fake_rate"]
                    - with_critic["fake_citation_rate"]["fake_rate"]
                ),
            }

            if not skip_judge:
                text_nc = render_output_for_judge(topic=topic, outline=no_critic.get("outline"))
                text_wc = render_output_for_judge(
                    topic=topic,
                    critiques=with_critic.get("critiques"),
                    outline=with_critic.get("outline"),
                )
                row["gap_depth"] = {
                    "no_critic": score_depth(text_nc, topic).score,
                    "with_critic": score_depth(text_wc, topic).score,
                }

            rows = upsert_row(rows, row)
            logger.info("RQ2 %s rep=%d grounding=%.3f", tid, rep, with_critic["evidence_grounding_rate"])

        save_topic_checkpoint("rq2", _payload(), tid)
        logger.info("RQ2 checkpoint saved for %s (%d rows total)", tid, len(rows))

    payload = _payload()
    save_run_result("rq2", f"run_{utc_now()[:10]}", payload)
    return payload
