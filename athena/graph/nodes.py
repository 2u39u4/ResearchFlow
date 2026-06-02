"""LangGraph-style nodes (W3: citation validation)."""

from __future__ import annotations

from typing import Any

from athena.graph.state import AthenaState, state_validation_payload
from athena.schemas.citation import Citation, ValidationResult
from athena.tools.citation_validator import validate_citations


def validate_citations_node(state: AthenaState) -> dict[str, Any]:
    """
    Read citations from state, run deterministic validator, write validation_report.
    """
    raw = state.get("citations") or []
    citations: list[Citation] = []
    for item in raw:
        if isinstance(item, Citation):
            citations.append(item)
        elif isinstance(item, dict):
            citations.append(Citation.model_validate(item))

    results: list[ValidationResult] = validate_citations(citations)
    return {"validation_report": results, "validation_report_json": state_validation_payload(results)}
