#!/usr/bin/env python3
"""RQ evaluation CLI: TopicSet pools, RQ1/RQ2/RQ3, figures, summary."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from eval.experiments.common import build_reference_pool, list_topics, pool_has_arxiv, pool_path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def cmd_build_pools(args: argparse.Namespace) -> int:
    topics = list_topics(limit=args.limit)
    if args.topic_ids:
        topics = [t for t in topics if t["id"] in args.topic_ids]
    failed = 0
    saw_429 = False
    retry_subset = bool(args.topic_ids)
    built_in_run = 0
    for spec in topics:
        tid = spec["id"]
        if not args.force and pool_has_arxiv(tid):
            logger.info("Skip %s — pool already has arXiv (%s)", tid, pool_path(tid))
            continue
        need_pause = built_in_run > 0 or (retry_subset and args.topic_sleep > 0)
        if need_pause:
            pause = args.sleep_after_429 if saw_429 else args.topic_sleep
            if pause > 0:
                logger.info(
                    "arXiv cooldown %ds before %s (spacing replicates t01 cold-start; "
                    "see eval/topics/protocol.md)",
                    pause,
                    tid,
                )
                time.sleep(pause)
            saw_429 = False
        try:
            pool = build_reference_pool(
                tid,
                spec["topic"],
                spec.get("domain", ""),
                per_source_limit=args.per_source,
                min_cards=args.min_cards,
            )
            logger.info(
                "Built pool %s: %d papers (arxiv=%s)",
                tid,
                len(pool["paper_ids"]),
                pool["sources_ok"].get("arxiv"),
            )
            built_in_run += 1
        except Exception as exc:
            failed += 1
            err = str(exc)
            if "429" in err:
                saw_429 = True
            logger.error("Failed %s: %s", tid, exc)
    return 1 if failed else 0


def cmd_rq1(args: argparse.Namespace) -> int:
    from eval.experiments.rq1 import run_rq1

    run_rq1(
        limit=args.limit,
        repeats=args.repeats,
        skip_judge=args.skip_judge,
        topic_ids=args.topic_ids,
        fresh=args.fresh,
    )
    return 0


def cmd_rq2(args: argparse.Namespace) -> int:
    from eval.experiments.rq2 import run_rq2

    run_rq2(
        limit=args.limit,
        repeats=args.repeats,
        skip_judge=args.skip_judge,
        topic_ids=args.topic_ids,
        fresh=args.fresh,
    )
    return 0


def cmd_rq3(args: argparse.Namespace) -> int:
    from eval.experiments.rq3 import run_rq3

    run_rq3(
        hallmark_path=args.hallmark,
        pipeline_path=args.pipeline,
    )
    return 0


def cmd_analysis(args: argparse.Namespace) -> int:
    from eval.analysis.plots import generate_all_figures
    from eval.analysis.report import write_report

    paths = generate_all_figures()
    for p in paths:
        logger.info("Wrote figure %s", p)
    report_path = write_report()
    logger.info("Wrote summary %s", report_path)
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    rc = cmd_build_pools(args)
    if rc != 0 and not args.allow_partial_pools:
        return rc
    if not args.rq3_only:
        cmd_rq1(args)
        cmd_rq2(args)
    cmd_rq3(args)
    cmd_analysis(args)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Athena RQ evaluation experiments")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--limit", type=int, default=None, help="Max topics (pilot: 3)")
        p.add_argument("--topic-ids", nargs="*", help="Subset e.g. t01 t02")
        p.add_argument(
            "--repeats",
            type=int,
            default=None,
            help="Repeats per topic (default EVAL_DEFAULT_REPEATS)",
        )
        p.add_argument("--skip-judge", action="store_true", help="Skip LLM judge (metrics only)")
        p.add_argument(
            "--fresh", action="store_true", help="Ignore checkpoint and start rows from scratch"
        )

    p_build = sub.add_parser("build-pools", help="Build reference paper pools")
    add_common(p_build)
    p_build.add_argument("--per-source", type=int, default=10)
    p_build.add_argument("--min-cards", type=int, default=8)
    p_build.add_argument(
        "--topic-sleep",
        type=int,
        default=90,
        help="Seconds between topics so each arXiv call gets fresh quota (default: 90)",
    )
    p_build.add_argument(
        "--sleep-after-429",
        type=int,
        default=120,
        help="Extra cooldown after a topic failed with 429 (default: 120)",
    )
    p_build.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if pool already has arXiv",
    )
    p_build.set_defaults(func=cmd_build_pools)

    for name, fn in [("rq1", cmd_rq1), ("rq2", cmd_rq2)]:
        p = sub.add_parser(name)
        add_common(p)
        p.set_defaults(func=fn)

    p_rq3 = sub.add_parser("rq3", help="HALLMARK + pipeline fake citation (no LLM)")
    p_rq3.add_argument(
        "--hallmark",
        type=Path,
        default=Path("examples/hallmark_metrics_sample.json"),
        help="HALLMARK metrics JSON (full run: results/athena_dev_public_full.json)",
    )
    p_rq3.add_argument(
        "--pipeline",
        type=Path,
        default=Path("examples/pipeline_report_sample.json"),
        help="Pipeline report JSON (full run: results/pipeline_report_v2.json)",
    )
    p_rq3.set_defaults(func=cmd_rq3)

    p_analysis = sub.add_parser("analysis", help="Figures + markdown summary")
    p_analysis.set_defaults(func=cmd_analysis)

    p_all = sub.add_parser("all", help="build-pools + rq1 + rq2 + rq3 + analysis")
    add_common(p_all)
    p_all.add_argument("--per-source", type=int, default=10)
    p_all.add_argument("--min-cards", type=int, default=8)
    p_all.add_argument("--allow-partial-pools", action="store_true")
    p_all.add_argument("--rq3-only", action="store_true")
    p_all.set_defaults(func=cmd_all)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
