"""Pipeline run endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.auth import get_current_user
from api.database import create_run, delete_run, get_run, list_runs
from api.pipeline_service import event_count, get_events, run_pipeline_async
from api.schemas import RunCreateRequest

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("")
async def create_run_endpoint(
    body: RunCreateRequest,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    run = create_run(user["id"], body.topic.strip(), body.constraints)
    run_pipeline_async(run["id"], user["id"], body.topic.strip(), body.constraints)
    return {
        "id": run["id"],
        "topic": run["topic"],
        "status": "pending",
        "created_at": run["created_at"],
    }


@router.get("")
async def list_runs_endpoint(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    items = list_runs(user["id"], limit=limit, offset=offset)
    return {"runs": items, "limit": limit, "offset": offset}


@router.get("/{run_id}")
async def get_run_endpoint(
    run_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    run = get_run(run_id, user["id"])
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run["id"],
        "topic": run["topic"],
        "status": run["status"],
        "constraints": run.get("constraints") or {},
        "report": run.get("report"),
        "error_message": run.get("error_message"),
        "paper_count": run.get("paper_count") or 0,
        "created_at": run["created_at"],
        "finished_at": run.get("finished_at"),
    }


@router.delete("/{run_id}")
async def delete_run_endpoint(
    run_id: str,
    user: dict = Depends(get_current_user),
) -> dict[str, str]:
    if not delete_run(run_id, user["id"]):
        raise HTTPException(status_code=404, detail="Run not found")
    return {"status": "deleted"}


@router.get("/{run_id}/events")
async def run_events_sse(
    run_id: str,
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    run = get_run(run_id, user["id"])
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        cursor = 0
        while True:
            batch = get_events(run_id, after=cursor)
            for item in batch:
                cursor += 1
                yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
            run_latest = get_run(run_id, user["id"])
            status = run_latest.get("status") if run_latest else "failed"
            if status in ("completed", "failed") and cursor >= event_count(run_id):
                yield f"data: {json.dumps({'step': 'done', 'status': status}, ensure_ascii=False)}\n\n"
                break
            await asyncio.sleep(0.8)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
