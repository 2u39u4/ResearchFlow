"""Map HALLMARK blind entries to Athena citations and back to predictions."""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any, Optional

from athena.config import Settings, get_settings
from athena.schemas.citation import Citation, ValidationResult, ValidationStatus
from athena.tools.citation_validator import CitationValidator, validate_citation

if TYPE_CHECKING:
    from hallmark.dataset.schema import BlindEntry, Prediction

# BibTeX "Author1 and Author2" — split on " and " (case-sensitive per BibTeX convention).
_AUTHOR_SPLIT = re.compile(r"\s+and\s+")


def parse_bibtex_authors(author_field: str) -> list[str]:
    if not author_field.strip():
        return []
    return [part.strip() for part in _AUTHOR_SPLIT.split(author_field) if part.strip()]


def blind_fields_to_citation(fields: dict[str, str]) -> Citation:
    """Build a Citation from HALLMARK blind `fields` (no ground-truth labels)."""
    year_raw = fields.get("year", "").strip()
    year: Optional[int] = int(year_raw) if year_raw.isdigit() else None
    venue = fields.get("booktitle", "") or fields.get("journal", "")
    return Citation(
        title=fields.get("title", "").strip(),
        authors=parse_bibtex_authors(fields.get("author", "")),
        year=year,
        doi=fields.get("doi", "").strip(),
        venue=venue.strip(),
    )


def blind_entry_to_citation(entry: Any) -> Citation:
    """Convert a HALLMARK `BlindEntry` (or compatible object) to `Citation`."""
    return blind_fields_to_citation(dict(entry.fields))


def validation_status_to_hallmark(
    status: ValidationStatus,
    *,
    match_score: float = 0.0,
) -> tuple[str, float]:
    """Return (HALLMARK label, confidence) for an Athena validation status."""
    if status == "verified":
        conf = min(0.99, 0.75 + match_score / 400.0)
        return "VALID", conf
    if status == "not_found":
        return "HALLUCINATED", 0.90
    if status == "mismatch":
        return "HALLUCINATED", 0.85
    raise ValueError(f"unknown validation status: {status!r}")


def validation_result_to_prediction(
    result: ValidationResult,
    bibtex_key: str,
) -> Prediction:
    """Map `ValidationResult` to a HALLMARK `Prediction`."""
    from hallmark.dataset.schema import Prediction

    label, confidence = validation_status_to_hallmark(
        result.status,
        match_score=result.match_score,
    )
    reason_parts = [f"athena:{result.status}"]
    if result.details.get("resolved_via"):
        reason_parts.append(str(result.details["resolved_via"]))
    if result.details.get("issues"):
        reason_parts.append("; ".join(str(x) for x in result.details["issues"]))
    elif result.details.get("reason"):
        reason_parts.append(str(result.details["reason"]))
    return Prediction(
        bibtex_key=bibtex_key,
        label=label,  # type: ignore[arg-type]
        confidence=confidence,
        reason=" | ".join(reason_parts),
    )


def run_athena_on_blind_entries(
    blind_entries: list[Any],
    *,
    settings: Optional[Settings] = None,
    delay_seconds: float = 0.0,
    validator: Optional[CitationValidator] = None,
) -> list[Prediction]:
    """Validate each blind entry with Athena and return HALLMARK predictions."""
    from hallmark.dataset.schema import Prediction

    settings = settings or get_settings()
    validator = validator or CitationValidator(settings)
    predictions: list[Prediction] = []

    for i, entry in enumerate(blind_entries):
        if delay_seconds > 0 and i > 0:
            time.sleep(delay_seconds)
        t0 = time.perf_counter()
        try:
            citation = blind_entry_to_citation(entry)
        except ValueError as exc:
            predictions.append(
                Prediction(
                    bibtex_key=entry.bibtex_key,
                    label="UNCERTAIN",
                    confidence=0.5,
                    reason=f"athena:invalid_citation ({exc})",
                    wall_clock_seconds=time.perf_counter() - t0,
                )
            )
            continue

        result = validator.validate(citation)
        pred = validation_result_to_prediction(result, entry.bibtex_key)
        pred.wall_clock_seconds = time.perf_counter() - t0
        predictions.append(pred)

    return predictions


def run_athena_on_blind_entries_cached(
    blind_entries: list[Any],
    *,
    settings: Optional[Settings] = None,
    delay_seconds: float = 0.0,
) -> list[Prediction]:
    """Same as `run_athena_on_blind_entries` using module-level `validate_citation` (tests)."""
    from hallmark.dataset.schema import Prediction

    settings = settings or get_settings()
    predictions: list[Prediction] = []

    for i, entry in enumerate(blind_entries):
        if delay_seconds > 0 and i > 0:
            time.sleep(delay_seconds)
        t0 = time.perf_counter()
        try:
            citation = blind_entry_to_citation(entry)
            result = validate_citation(citation, settings)
            pred = validation_result_to_prediction(result, entry.bibtex_key)
        except ValueError as exc:
            pred = Prediction(
                bibtex_key=entry.bibtex_key,
                label="UNCERTAIN",
                confidence=0.5,
                reason=f"athena:invalid_citation ({exc})",
            )
        pred.wall_clock_seconds = time.perf_counter() - t0
        predictions.append(pred)

    return predictions
