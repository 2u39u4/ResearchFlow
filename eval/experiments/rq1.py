"""RQ1: Multi-Agent vs Single-Agent (Coverage, Depth, Pairwise Preference)."""

from __future__ import annotations

import logging
from typing import Any

from athena.agents.critic import run_critic
from athena.agents.writer import run_writer
from athena.config import get_settings
from eval.experiments.baselines.single_agent import run_single_agent
from eval.experiments.common import (
    coerce_cards,
    collect_output_paper_ids,
    coverage_rate,
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
from eval.judges.llm_judge import pairwise_preference, render_output_for_judge, score_depth

logger = logging.getLogger(__name__)


def run_multi_agent(topic: str, cards: list) -> dict[str, Any]:
    critic = run_critic(topic, cards)
    writer = run_writer(topic, cards, critic.critiques)
    return {
        "critiques": [c.model_dump() for c in critic.critiques],
        "outline": writer.outline.model_dump() if writer.outline else None,
        "evidence_grounding_rate": critic.evidence_grounding_rate,
        "critic_model": critic.model,
        "writer_model": writer.model,
        "errors": critic.errors + writer.errors,
    }


def run_rq1(
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

    rows, created_at = resume_rows("rq1", repeats=repeats, skip_judge=skip_judge, fresh=fresh)
    if created_at:
        logger.info("RQ1 resume: %d prior rows from checkpoint", len(rows))

    def _payload() -> dict[str, Any]:
        return {
            "rq": "RQ1",
            "description": "Multi-Agent (Critic+Writer) vs Single-Agent baseline",
            "repeats": repeats,
            "skip_judge": skip_judge,
            "judge_model": settings.judge_llm_model or settings.default_llm_model,
            "subject_model": settings.default_llm_model,
            "created_at": created_at or utc_now(),
            "updated_at": utc_now(),
            "topic_count": len(topics),
            "rows": rows,
        }

    for spec in topics:
        tid = spec["id"]
        if topic_is_complete(rows, tid, repeats):
            logger.info("RQ1 skip %s — already complete (%d repeats)", tid, repeats)
            continue

        topic = spec["topic"]
        pool = load_reference_pool(tid)
        pool_ids = set(pool["paper_ids"])
        cards = coerce_cards(pool["cards"])
        done_reps = topic_repeats_done(rows, tid, repeats)

        for rep in range(repeats):
            if rep in done_reps:
                logger.info("RQ1 skip %s rep=%d — checkpoint hit", tid, rep)
                continue

            multi = run_multi_agent(topic, cards)
            single = run_single_agent(topic, cards)

            multi_ids = collect_output_paper_ids(
                critiques=multi.get("critiques"),
                outline=multi.get("outline"),
            )
            single_ids = collect_output_paper_ids(
                critiques=single.critiques,
                outline=single.outline,
            )

            row: dict[str, Any] = {
                "topic_id": tid,
                "topic": topic,
                "domain": spec.get("domain"),
                "repeat": rep,
                "coverage": {
                    "multi_agent": coverage_rate(multi_ids, pool_ids),
                    "single_agent": coverage_rate(single_ids, pool_ids),
                },
                "multi_agent": multi,
                "single_agent": {
                    "critiques": [c.model_dump() for c in single.critiques],
                    "outline": single.outline.model_dump() if single.outline else None,
                    "errors": single.errors,
                },
            }

            if not skip_judge:
                multi_text = render_output_for_judge(
                    topic=topic,
                    critiques=multi.get("critiques"),
                    outline=multi.get("outline"),
                )
                single_text = render_output_for_judge(
                    topic=topic,
                    critiques=[c.model_dump() for c in single.critiques],
                    outline=single.outline.model_dump() if single.outline else None,
                )
                row["depth"] = {
                    "multi_agent": score_depth(multi_text, topic).score,
                    "single_agent": score_depth(single_text, topic).score,
                }
                pw = pairwise_preference(
                    multi_text,
                    single_text,
                    topic,
                    label_a="multi_agent",
                    label_b="single_agent",
                    seed=settings.eval_random_seed + rep,
                )
                row["pairwise"] = {
                    "winner": pw.winner,
                    "rationale": pw.rationale,
                    "presentation": pw.presentation,
                }

            rows = upsert_row(rows, row)
            logger.info(
                "RQ1 %s rep=%d coverage multi=%.3f single=%.3f",
                tid,
                rep,
                row["coverage"]["multi_agent"],
                row["coverage"]["single_agent"],
            )

        save_topic_checkpoint("rq1", _payload(), tid)
        logger.info("RQ1 checkpoint saved for %s (%d rows total)", tid, len(rows))

    payload = _payload()
    save_run_result("rq1", f"run_{utc_now()[:10]}", payload)
    return payload


def aggregate_rq1(payload: dict[str, Any]) -> dict[str, Any]:
    from eval.analysis.stats import mean_std

    rows = payload.get("rows") or []
    cov_m = [r["coverage"]["multi_agent"] for r in rows]
    cov_s = [r["coverage"]["single_agent"] for r in rows]
    summary: dict[str, Any] = {
        "coverage_multi": mean_std(cov_m),
        "coverage_single": mean_std(cov_s),
    }
    if rows and "depth" in rows[0]:
        summary["depth_multi"] = mean_std([r["depth"]["multi_agent"] for r in rows])
        summary["depth_single"] = mean_std([r["depth"]["single_agent"] for r in rows])
        wins = [r["pairwise"]["winner"] for r in rows if "pairwise" in r]
        summary["pairwise_win_rate_multi"] = wins.count("multi_agent") / len(wins) if wins else 0.0
    return summary
