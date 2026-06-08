"""Research dedup and KnowledgeCard tests — no network."""

from athena.schemas.knowledge_card import KnowledgeCard
from athena.tools.dedup import deduplicate_cards
from athena.tools.normalize import dedup_key, normalize_doi, normalize_title


def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1234/abc") == "10.1234/abc"


def test_normalize_title():
    assert normalize_title("Hello, World!") == normalize_title("hello world")


def test_dedup_key_prefers_doi():
    k = dedup_key("10.1234/x", "Some Title")
    assert k.startswith("doi:")


def test_deduplicate_merges_same_doi():
    a = KnowledgeCard(
        paper_id="arxiv:1",
        title="Paper A",
        doi="10.1234/x",
        source="arxiv",
        abstract="",
    )
    b = KnowledgeCard(
        paper_id="doi:10.1234/x",
        title="Paper A Longer",
        doi="10.1234/x",
        source="crossref",
        abstract="Full abstract here",
        authors=["Alice"],
        year=2024,
    )
    out = deduplicate_cards([a, b])
    assert len(out) == 1
    assert out[0].source == "crossref"
    assert out[0].abstract == "Full abstract here"


def test_deduplicate_merges_same_title():
    a = KnowledgeCard(paper_id="a", title="Graph RAG Survey", source="arxiv")
    b = KnowledgeCard(paper_id="b", title="graph rag survey", source="semantic_scholar")
    out = deduplicate_cards([a, b])
    assert len(out) == 1
