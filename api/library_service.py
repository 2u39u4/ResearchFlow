"""Per-user PDF RAG library."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from api.config import get_api_settings
from api.database import delete_library_doc, list_library_docs, upsert_library_doc
from app.pdf_indexing import MAX_PDF_UPLOADS, index_pdf_bytes, remaining_pdf_slots
from app.upload_utils import resolve_upload_path

_index_lock = threading.Lock()
_user_indices: dict[str, object] = {}


def user_upload_dir(user_id: str) -> Path:
    settings = get_api_settings()
    path = settings.athena_data_dir / "users" / user_id / "uploads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_index(user_id: str):
    from athena.rag import PdfRagIndex

    with _index_lock:
        if user_id not in _user_indices:
            idx = PdfRagIndex()
            upload_dir = user_upload_dir(user_id)
            for pdf in sorted(upload_dir.glob("*.pdf")):
                if pdf.name in idx.doc_ids:
                    continue
                try:
                    index_pdf_bytes(
                        idx,
                        filename=pdf.name,
                        data=pdf.read_bytes(),
                        upload_dir=upload_dir,
                    )
                except Exception:
                    continue
            _user_indices[user_id] = idx
        return _user_indices[user_id]


def invalidate_index(user_id: str) -> None:
    with _index_lock:
        _user_indices.pop(user_id, None)


def add_pdf(user_id: str, filename: str, data: bytes) -> dict[str, Any]:
    index = get_user_index(user_id)
    upload_dir = user_upload_dir(user_id)
    result = index_pdf_bytes(index, filename=filename, data=data, upload_dir=upload_dir)
    if result.error:
        return {"ok": False, "error": result.error, "filename": filename}
    if result.chunks_added > 0 or result.already_indexed:
        upsert_library_doc(
            user_id,
            result.path.name if result.path else filename,
            filename,
            index.chunk_count,
        )
    return {
        "ok": True,
        "filename": filename,
        "chunks_added": result.chunks_added,
        "already_indexed": result.already_indexed,
        "doc_count": len(index.doc_ids),
        "chunk_count": index.chunk_count,
        "slots_remaining": remaining_pdf_slots(index, max_docs=MAX_PDF_UPLOADS),
    }


def search_library(user_id: str, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    index = get_user_index(user_id)
    hits = index.query(query, top_k=top_k)
    return [
        {
            "score": h.score,
            "doc_id": h.chunk.doc_id,
            "page": h.chunk.page,
            "text": h.chunk.text,
        }
        for h in hits
    ]


def list_docs(user_id: str) -> dict[str, Any]:
    index = get_user_index(user_id)
    docs = list_library_docs(user_id)
    return {
        "docs": docs,
        "doc_ids": index.doc_ids,
        "chunk_count": index.chunk_count,
        "max_docs": MAX_PDF_UPLOADS,
        "slots_remaining": remaining_pdf_slots(index),
    }


def remove_doc(user_id: str, doc_id: str) -> bool:
    upload_dir = user_upload_dir(user_id)
    dest = resolve_upload_path(upload_dir, doc_id)
    if dest.is_file():
        dest.unlink()
    delete_library_doc(user_id, doc_id)
    invalidate_index(user_id)
    return True
