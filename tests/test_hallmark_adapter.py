"""Offline tests for HALLMARK ↔ Athena adapter (no network)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from eval.citebench.hallmark_adapter import (
    blind_fields_to_citation,
    parse_bibtex_authors,
    validation_result_to_prediction,
    validation_status_to_hallmark,
)
from athena.schemas.citation import Citation, ValidationResult


@dataclass
class _FakeBlind:
    bibtex_key: str
    bibtex_type: str = "inproceedings"
    fields: dict[str, str] = field(default_factory=dict)
    raw_bibtex: str | None = None


def test_parse_bibtex_authors():
    assert parse_bibtex_authors("A and B and C") == ["A", "B", "C"]
    assert parse_bibtex_authors("") == []


def test_blind_fields_to_citation():
    c = blind_fields_to_citation(
        {
            "title": "Attention Is All You Need",
            "author": "Ashish Vaswani and Noam Shazeer",
            "year": "2017",
            "doi": "10.48550/arXiv.1706.03762",
            "booktitle": "NeurIPS",
        }
    )
    assert c.title == "Attention Is All You Need"
    assert len(c.authors) == 2
    assert c.year == 2017
    assert "arxiv" in c.doi.lower()
    assert c.venue == "NeurIPS"


@pytest.mark.parametrize(
    "status,label,conf_min",
    [
        ("verified", "VALID", 0.8),
        ("not_found", "HALLUCINATED", 0.89),
        ("mismatch", "HALLUCINATED", 0.84),
    ],
)
def test_validation_status_to_hallmark(status, label, conf_min):
    got_label, conf = validation_status_to_hallmark(status, match_score=100.0)
    assert got_label == label
    assert conf >= conf_min


def test_validation_result_to_prediction_requires_hallmark():
    pytest.importorskip("hallmark")
    result = ValidationResult(
        status="not_found",
        citation=Citation(title="Fake Paper XYZ", authors=["Nobody"]),
        details={"reason": "no_title_match"},
    )
    pred = validation_result_to_prediction(result, "key123")
    assert pred.bibtex_key == "key123"
    assert pred.label == "HALLUCINATED"
    assert "athena:not_found" in pred.reason


def test_fake_blind_entry_to_citation():
    blind = _FakeBlind(
        bibtex_key="abc",
        fields={"title": "Some Paper", "author": "Jane Doe", "year": "2020"},
    )
    from eval.citebench.hallmark_adapter import blind_entry_to_citation

    c = blind_entry_to_citation(blind)
    assert c.title == "Some Paper"
    assert c.authors == ["Jane Doe"]
