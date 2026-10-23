import asyncio
import json
from dataclasses import asdict
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.ingest.count import ExactCount, count_all
from app.net.safe_fetch import BlockedURL, FetchError, check_url, make_client, resolve_public
from app.pipeline.runner import run_audit
from app.store import store

router = APIRouter(prefix="/audits", tags=["audits"])
_tasks: set[asyncio.Task] = set()


class AuditIn(BaseModel):
    url: str = Field(..., max_length=2048, description="Site URL or sitemap URL")


@router.post("", status_code=202)
async def create_audit(body: AuditIn):
    url = body.url.strip()
    try:
        check_url(url)
        # Resolve now so internal targets are refused up front, not mid-audit.
        await resolve_public(urlsplit(url).hostname or "")
    except BlockedURL as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except FetchError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    rec = store.create(url)
    task = asyncio.create_task(run_audit(rec))
    _tasks.add(task)  # keep a reference so the task isn't garbage-collected
    task.add_done_callback(_tasks.discard)
    return {"id": rec.id, "status": rec.status}


@router.get("/{audit_id}")
async def get_audit(audit_id: str):
    rec = store.get(audit_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Audit not found")
    return rec.public()


@router.get("/{audit_id}/events")
async def audit_events(audit_id: str):
    rec = store.get(audit_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Audit not found")

    async def stream():
        seq = 0
        while True:
            if not await rec.wait_for(seq):
                yield ": keep-alive\n\n"
                continue
            while seq < len(rec.events):
                ev = rec.events[seq]
                seq += 1
                yield f"data: {json.dumps(ev)}\n\n"
                if ev["type"] in ("done", "error"):
                    return

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{audit_id}/count", status_code=202)
async def count_pages(audit_id: str):
    """Read every sitemap file and count URLs exactly (the audit itself samples them)."""
    rec = store.get(audit_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Audit not found")
    if rec.status != "done":
        raise HTTPException(status_code=409, detail="The audit hasn't finished yet")
    sm = rec.result.get("sitemap") or {}
    if sm.get("source") != "sitemap" or not sm.get("start"):
        raise HTTPException(status_code=422, detail="This site has no sitemap, so there's nothing more to count")
    current = rec.result.get("exact_count")
    if current and current.get("status") in ("running", "done"):
        return current

    patterns = [t["pattern"] for t in rec.result.get("templates", [])]
    state = ExactCount()
    rec.result["exact_count"] = asdict(state)

    async def progress(st: ExactCount):
        rec.result["exact_count"] = asdict(st)

    async def run():
        try:
            async with make_client() as client:
                await count_all(client, sm["start"], patterns, state, on_progress=progress)
        except Exception as e:  # noqa: BLE001 — report, don't crash the API
            state.status, state.error = "error", f"Counting failed: {type(e).__name__}"
        rec.result["exact_count"] = asdict(state)

    task = asyncio.create_task(run())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return rec.result["exact_count"]
