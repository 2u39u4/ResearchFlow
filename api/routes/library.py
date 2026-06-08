"""Private PDF library endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from api.auth import get_current_user
from api.library_service import add_pdf, list_docs, remove_doc, search_library
from api.schemas import LibrarySearchRequest

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/pdfs")
async def list_pdfs(user: dict = Depends(get_current_user)) -> dict[str, Any]:
    return list_docs(user["id"])


@router.post("/pdfs")
async def upload_pdf(
    user: dict = Depends(get_current_user),
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    results = []
    for f in files:
        if not f.filename or not f.filename.lower().endswith(".pdf"):
            results.append({"ok": False, "error": "PDF only", "filename": f.filename})
            continue
        data = await f.read()
        results.append(add_pdf(user["id"], f.filename, data))
    return {"results": results, "library": list_docs(user["id"])}


@router.post("/search")
async def search_pdfs(
    body: LibrarySearchRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    hits = search_library(user["id"], body.query, top_k=body.top_k)
    return {"query": body.query, "hits": hits}


@router.delete("/pdfs/{doc_id}")
async def delete_pdf(
    doc_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, str]:
    remove_doc(user["id"], doc_id)
    return {"status": "deleted"}
