"""Converters build cards from API-shaped dicts only."""

from athena.tools.arxiv_search import ArxivPaper
from athena.tools.converters import arxiv_to_card, semantic_scholar_to_card


def test_arxiv_to_card_metadata_from_api():
    paper = ArxivPaper(
        arxiv_id="2401.00001",
        title="Test Title",
        authors=["A Author"],
        published="2024-03-01T00:00:00+00:00",
        summary="Abstract text",
        pdf_url="https://arxiv.org/pdf/2401.00001",
    )
    card = arxiv_to_card(paper)
    assert card.paper_id == "arxiv:2401.00001"
    assert card.title == "Test Title"
    assert card.year == 2024
    assert card.source == "arxiv"
    assert card.contributions == []


def test_semantic_scholar_to_card_uses_external_ids():
    item = {
        "paperId": "abc123",
        "title": "Transformer Paper",
        "authors": [{"name": "Alice"}],
        "year": 2023,
        "venue": "NeurIPS",
        "abstract": "We propose...",
        "externalIds": {"DOI": "10.5555/xyz", "ArXiv": "2301.00001"},
    }
    card = semantic_scholar_to_card(item)
    assert card is not None
    assert card.paper_id == "doi:10.5555/xyz"
    assert card.doi == "10.5555/xyz"
    assert card.authors == ["Alice"]
