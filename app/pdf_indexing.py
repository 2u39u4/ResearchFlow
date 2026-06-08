"""Index uploaded PDFs into the local private RAG store."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.upload_utils import resolve_upload_path
from athena.rag import PdfRagIndex

MAX_PDF_UPLOADS = 5


@dataclass
class PdfIndexResult:
    filename: str
    path: Path | None
    chunks_added: int
    already_indexed: bool
    error: str | None = None


def index_pdf_bytes(
    index: PdfRagIndex,
    *,
    filename: str,
    data: bytes,
    upload_dir: Path,
) -> PdfIndexResult:
    """Save one PDF and add it to the index. Skips if doc_id already present."""
    try:
        dest = resolve_upload_path(upload_dir, filename)
        dest.write_bytes(data)
        if dest.name in index.doc_ids:
            return PdfIndexResult(
                filename=filename,
                path=dest,
                chunks_added=0,
                already_indexed=True,
            )
        n_chunks = index.add_pdf_bytes(data, doc_id=dest.name, source=str(dest))
        return PdfIndexResult(
            filename=filename,
            path=dest,
            chunks_added=n_chunks,
            already_indexed=False,
        )
    except Exception as exc:  # noqa: BLE001 — return per-file errors to the UI
        return PdfIndexResult(
            filename=filename,
            path=None,
            chunks_added=0,
            already_indexed=False,
            error=str(exc),
        )


def remaining_pdf_slots(index: PdfRagIndex, *, max_docs: int = MAX_PDF_UPLOADS) -> int:
    """How many more PDFs can be added to the index."""
    return max(0, max_docs - len(index.doc_ids))


def index_pdf_uploads(
    index: PdfRagIndex,
    uploads: list[tuple[str, bytes]],
    *,
    upload_dir: Path,
    max_docs: int = MAX_PDF_UPLOADS,
) -> list[PdfIndexResult]:
    """Index multiple PDF uploads in order, respecting the per-session PDF cap."""
    results: list[PdfIndexResult] = []
    for name, data in uploads:
        if remaining_pdf_slots(index, max_docs=max_docs) <= 0:
            results.append(
                PdfIndexResult(
                    filename=name,
                    path=None,
                    chunks_added=0,
                    already_indexed=False,
                    error=f"Index full (max {max_docs} PDFs).",
                )
            )
            continue
        results.append(index_pdf_bytes(index, filename=name, data=data, upload_dir=upload_dir))
    return results
