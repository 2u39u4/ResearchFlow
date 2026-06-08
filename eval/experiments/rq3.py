"""RQ3: HALLMARK validator metrics + pipeline fake-citation reduction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eval.experiments.common import (
    fake_rate_with_validator_filter,
    save_run_result,
    utc_now,
)

DEFAULT_HALLMARK = Path("examples/hallmark_metrics_sample.json")
DEFAULT_PIPELINE = Path("examples/pipeline_report_sample.json")


def load_hallmark_metrics(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return {
        "source": str(path),
        "split": data.get("split_name", "dev_public"),
        "num_entries": data.get("num_entries"),
        "detection_rate": data.get("detection_rate"),
        "f1_hallucination": data.get("f1_hallucination"),
        "tier_weighted_f1": data.get("tier_weighted_f1"),
        "false_positive_rate": data.get("false_positive_rate"),
        "ece": data.get("ece"),
        "per_tier_metrics": data.get("per_tier_metrics"),
    }


def pipeline_citation_analysis(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        report = json.load(f)
    validation = report.get("validation_report") or []
    rows = [v if isinstance(v, dict) else v for v in validation]
    comparison = fake_rate_with_validator_filter(rows)
    return {
        "source": str(path),
        "topic": report.get("topic"),
        "run_id": report.get("run_id"),
        "num_citations": comparison["without_validation"]["total"],
        "comparison": comparison,
    }


def run_rq3(
    *,
    hallmark_path: Path | None = None,
    pipeline_path: Path | None = None,
) -> dict[str, Any]:
    hallmark_path = hallmark_path or DEFAULT_HALLMARK
    pipeline_path = pipeline_path or DEFAULT_PIPELINE

    payload: dict[str, Any] = {
        "rq": "RQ3",
        "description": "Citation Validator on HALLMARK + system-level fake citation reduction",
        "created_at": utc_now(),
        "hallmark": None,
        "pipeline": None,
        "notes": [],
    }

    if hallmark_path.is_file():
        payload["hallmark"] = load_hallmark_metrics(hallmark_path)
    else:
        payload["notes"].append(f"HALLMARK metrics missing: {hallmark_path}")

    if pipeline_path.is_file():
        payload["pipeline"] = pipeline_citation_analysis(pipeline_path)
    else:
        payload["notes"].append(f"Pipeline report missing: {pipeline_path}")

    save_run_result("rq3", f"run_{utc_now()[:10]}", payload)
    return payload
