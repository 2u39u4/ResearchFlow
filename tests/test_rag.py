"""Tests for the local PDF RAG module (offline, hashing backend)."""

from __future__ import annotations

import numpy as np
import pytest

from athena.rag import (
    HashingEmbedder,
    PdfRagIndex,
    RagDocument,
    VectorStore,
    chunk_text,
    document_from_text,
    get_embedder,
)
from athena.rag.chunking import chunk_document, normalize_whitespace


def test_normalize_whitespace_collapses():
    assert normalize_whitespace("a\n\n  b\t c") == "a b c"


def test_chunk_text_overlap_and_bounds():
    text = "word " * 400  # ~2000 chars after normalization
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) > 1
    # Each chunk within size; consecutive chunks overlap.
    for span, c0, c1 in chunks:
        assert c1 - c0 <= 200
        assert text_span_ok(span)
    assert chunks[1][1] < chunks[0][2]  # start of chunk 2 < end of chunk 1


def text_span_ok(span: str) -> bool:
    return isinstance(span, str) and len(span) > 0


def test_chunk_text_rejects_bad_overlap():
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=10, overlap=10)


def test_chunk_document_keeps_pages():
    doc = RagDocument(doc_id="d1", pages=["alpha " * 100, "beta " * 100])
    chunks = chunk_document(doc, chunk_size=120, overlap=20)
    pages = {c.page for c in chunks}
    assert pages == {0, 1}
    assert all(c.doc_id == "d1" for c in chunks)


def test_hashing_embedder_deterministic_and_normalized():
    emb = HashingEmbedder(dim=128)
    v1 = emb.embed(["retrieval augmented generation"])
    v2 = emb.embed(["retrieval augmented generation"])
    assert v1.shape == (1, 128)
    np.testing.assert_allclose(v1, v2)
    np.testing.assert_allclose(np.linalg.norm(v1, axis=1), [1.0], atol=1e-5)


def test_hashing_embedder_similarity_orders_by_overlap():
    emb = HashingEmbedder(dim=512)
    q = emb.embed(["graph neural networks for molecules"])[0]
    near = emb.embed(["graph neural networks predict molecule properties"])[0]
    far = emb.embed(["distributed consensus in databases"])[0]
    assert float(near @ q) > float(far @ q)


def test_vector_store_add_and_search():
    emb = HashingEmbedder(dim=256)
    doc = document_from_text(
        "transformers use self attention. attention is all you need.", doc_id="t"
    )
    chunks = chunk_document(doc, chunk_size=200, overlap=20)
    store = VectorStore(emb.dim)
    store.add(chunks, emb.embed([c.text for c in chunks]))
    assert len(store) == len(chunks)
    hits = store.search(emb.embed(["self attention"])[0], top_k=3)
    assert hits and hits[0].score >= hits[-1].score


def test_pdf_rag_index_end_to_end_text():
    index = PdfRagIndex(embedder=HashingEmbedder(dim=512))
    added = index.add_text(
        "Retrieval augmented generation grounds LLM answers in retrieved documents. "
        "Vector search finds relevant passages. Citation verification reduces hallucination.",
        doc_id="notes",
    )
    assert added >= 1
    assert index.chunk_count == added
    assert index.doc_ids == ["notes"]
    hits = index.query("how does retrieval reduce hallucination", top_k=2)
    assert hits
    assert hits[0].chunk.doc_id == "notes"


def test_pdf_rag_index_empty_query_returns_empty():
    index = PdfRagIndex(embedder=HashingEmbedder(dim=64))
    index.add_text("some content here", doc_id="d")
    assert index.query("   ") == []


def test_get_embedder_unknown_backend():
    with pytest.raises(ValueError):
        get_embedder("does-not-exist")


def test_get_embedder_auto_falls_back_to_hashing(monkeypatch):
    # When sentence-transformers is unavailable, "auto" must use the offline backend.
    monkeypatch.setattr("athena.rag.embeddings.sentence_transformers_available", lambda: False)
    emb = get_embedder("auto", dim=128)
    assert isinstance(emb, HashingEmbedder)
    assert emb.dim == 128
    assert emb.embed(["hello world"]).shape == (1, 128)


def test_pdf_extraction_roundtrip():
    """Generate a tiny PDF with PyMuPDF and read it back (skips if unavailable)."""
    fitz = pytest.importorskip("fitz")
    from athena.rag.pdf import document_from_bytes

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello RAG world. Attention mechanisms.")
    data = doc.tobytes()
    doc.close()

    rag_doc = document_from_bytes(data, doc_id="gen", source="gen.pdf")
    assert rag_doc.doc_id == "gen"
    assert "Hello RAG world" in rag_doc.text
