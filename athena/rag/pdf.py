"""PDF text extraction via PyMuPDF (lazy import)."""

from __future__ import annotations

from pathlib import Path

from athena.rag.schemas import RagDocument


def extract_pdf_pages(data: bytes) -> list[str]:
    """Extract per-page text from raw PDF bytes. Requires PyMuPDF (pymupdf)."""
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:  # pragma: no cover - exercised only without pymupdf
        raise ImportError(
            "PyMuPDF (pymupdf) is required for PDF extraction. Install: pip install pymupdf"
        ) from exc

    pages: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page in doc:
            pages.append(page.get_text("text") or "")
    return pages


def load_pdf_document(path: Path | str, *, doc_id: str | None = None) -> RagDocument:
    """Read a PDF file from disk into a RagDocument."""
    path = Path(path)
    data = path.read_bytes()
    return RagDocument(
        doc_id=doc_id or path.stem,
        source=str(path),
        pages=extract_pdf_pages(data),
    )


def document_from_bytes(
    data: bytes,
    *,
    doc_id: str,
    source: str = "",
) -> RagDocument:
    """Build a RagDocument from in-memory PDF bytes (e.g. a Streamlit upload)."""
    return RagDocument(doc_id=doc_id, source=source, pages=extract_pdf_pages(data))


def document_from_text(text: str, *, doc_id: str, source: str = "") -> RagDocument:
    """Build a single-page RagDocument from plain text (no PDF dependency)."""
    return RagDocument(doc_id=doc_id, source=source, pages=[text])
