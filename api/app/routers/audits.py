import asyncio
import json
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.net.safe_fetch import BlockedURL, FetchError, check_url, resolve_public
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
