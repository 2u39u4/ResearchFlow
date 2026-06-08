"""Citation validator tests — offline with mocked APIs."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from athena.graph.nodes import validate_citations_node
from athena.schemas.citation import Citation
from athena.tools.citation_validator import validate_citation

ATTENTION_CROSSREF = {
    "DOI": "10.48550/arxiv.1706.03762",
    "title": ["Attention Is All You Need"],
    "author": [
        {"given": "Ashish", "family": "Vaswani"},
        {"given": "Noam", "family": "Shazeer"},
    ],
    "issued": {"date-parts": [[2017]]},
    "container-title": ["arXiv"],
    "URL": "https://doi.org/10.48550/arxiv.1706.03762",
}


def test_citation_requires_doi_or_title():
    with pytest.raises(ValueError):
        Citation(title="", doi="")


@patch("athena.tools.citation_validator._resolve_by_doi")
@patch("athena.tools.citation_validator.search_by_title")
def test_verified_by_doi(mock_search, mock_resolve):
    from athena.tools.citation_validator import ResolvedWork

    mock_resolve.return_value = ResolvedWork(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        year=2017,
        doi="10.48550/arxiv.1706.03762",
        source="crossref",
    )
    mock_search.return_value = []

    citation = Citation(
        doi="10.48550/arxiv.1706.03762",
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        year=2017,
    )
    result = validate_citation(citation)
    assert result.status == "verified"
    assert "doi" in result.details.get("resolved_via", "")
    mock_search.assert_not_called()


@patch("athena.tools.citation_validator._safe_lookup_doi")
@patch("athena.tools.citation_validator.s2_search_papers")
@patch("athena.tools.citation_validator.search_by_title")
def test_not_found_hallucinated_title(mock_cr, mock_s2, mock_doi):
    mock_doi.return_value = None
    mock_cr.return_value = []
    mock_s2.return_value = []

    citation = Citation(
        title="Completely Fabricated Paper Title XYZ 99999",
        authors=["Nobody Real"],
        year=2099,
    )
    result = validate_citation(citation)
    assert result.status == "not_found"
    assert result.details.get("reason") == "no_title_match"


@patch("athena.tools.citation_validator._safe_lookup_doi")
@patch("athena.tools.citation_validator.s2_search_papers")
@patch("athena.tools.citation_validator.search_by_title")
def test_mismatch_wrong_year(mock_cr, mock_s2, mock_doi):
    mock_doi.return_value = None
    mock_cr.return_value = [ATTENTION_CROSSREF]
    mock_s2.return_value = []

    citation = Citation(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani"],
        year=1990,
    )
    result = validate_citation(citation)
    assert result.status == "mismatch"
    assert "year" in str(result.details.get("issues", []))


@patch("athena.tools.citation_validator._resolve_by_doi")
@patch("athena.tools.citation_validator.search_by_title")
def test_mismatch_wrong_author(mock_search, mock_resolve):
    from athena.tools.citation_validator import ResolvedWork

    mock_resolve.return_value = ResolvedWork(
        title="Attention Is All You Need",
        authors=["Ashish Vaswani", "Noam Shazeer"],
        year=2017,
        doi="10.48550/arxiv.1706.03762",
        source="crossref",
    )
    mock_search.return_value = []

    citation = Citation(
        doi="10.48550/arxiv.1706.03762",
        title="Attention Is All You Need",
        authors=["ZZZZ Unknown Author"],
        year=2017,
    )
    result = validate_citation(citation)
    assert result.status == "mismatch"
    assert "authors" in str(result.details.get("issues", []))


@patch("athena.graph.nodes.validate_citations")
def test_validate_citations_node(mock_validate):
    from athena.schemas.citation import ValidationResult

    c = Citation(title="Test", doi="10.1/test")
    mock_validate.return_value = [
        ValidationResult(status="verified", citation=c, details={}),
    ]
    out = validate_citations_node({"citations": [c.model_dump()]})
    assert len(out["validation_report"]) == 1
    assert out["validation_report"][0].status == "verified"


def test_validator_has_no_llm_imports():
    import ast
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "athena/tools/citation_validator.py"
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "openai" not in alias.name
                assert "llm" not in alias.name
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "athena.llm" not in mod
