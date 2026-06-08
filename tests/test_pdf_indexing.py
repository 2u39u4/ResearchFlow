"""Tests for multi-PDF indexing helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.pdf_indexing import (
    MAX_PDF_UPLOADS,
    index_pdf_bytes,
    index_pdf_uploads,
    remaining_pdf_slots,
)
from athena.rag import HashingEmbedder, PdfRagIndex


def _tiny_pdf_bytes() -> bytes:
    fitz = pytest.importorskip("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Private RAG chunk one. Private RAG chunk two.")
    data = doc.tobytes()
    doc.close()
    return data


def test_index_pdf_bytes_adds_chunks(tmp_path: Path):
    index = PdfRagIndex(embedder=HashingEmbedder(dim=64))
    data = _tiny_pdf_bytes()
    result = index_pdf_bytes(
        index,
        filename="paper-a.pdf",
        data=data,
        upload_dir=tmp_path,
    )
    assert result.error is None
    assert result.path is not None
    assert result.chunks_added >= 1
    assert not result.already_indexed
    assert "paper-a.pdf" in index.doc_ids


def test_index_pdf_bytes_skips_duplicate(tmp_path: Path):
    index = PdfRagIndex(embedder=HashingEmbedder(dim=64))
    data = _tiny_pdf_bytes()
    first = index_pdf_bytes(index, filename="dup.pdf", data=data, upload_dir=tmp_path)
    second = index_pdf_bytes(index, filename="dup.pdf", data=data, upload_dir=tmp_path)
    assert first.chunks_added >= 1
    assert second.already_indexed
    assert second.chunks_added == 0


def test_remaining_pdf_slots():
    index = PdfRagIndex(embedder=HashingEmbedder(dim=64))
    assert remaining_pdf_slots(index) == MAX_PDF_UPLOADS
    index.add_text("x", doc_id="d1")
    assert remaining_pdf_slots(index) == MAX_PDF_UPLOADS - 1


def test_index_pdf_uploads_respects_max(tmp_path: Path):
    index = PdfRagIndex(embedder=HashingEmbedder(dim=64))
    data = _tiny_pdf_bytes()
    uploads = [(f"p{i}.pdf", data) for i in range(MAX_PDF_UPLOADS + 2)]
    results = index_pdf_uploads(index, uploads, upload_dir=tmp_path)
    assert len(results) == MAX_PDF_UPLOADS + 2
    assert len(index.doc_ids) == MAX_PDF_UPLOADS
    assert results[-1].error and "max" in results[-1].error.lower()


def test_index_pdf_uploads_multiple(tmp_path: Path):
    index = PdfRagIndex(embedder=HashingEmbedder(dim=64))
    data = _tiny_pdf_bytes()
    results = index_pdf_uploads(
        index,
        [("a.pdf", data), ("b.pdf", data)],
        upload_dir=tmp_path,
    )
    assert len(results) == 2
    assert all(r.error is None for r in results)
    assert all(r.chunks_added >= 1 for r in results)
    assert set(index.doc_ids) == {"a.pdf", "b.pdf"}
