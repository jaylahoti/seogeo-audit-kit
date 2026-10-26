"""Audit storage: live audits in memory, every audit saved to a database.

Running audits live in memory so their events can stream; each one is written to the
database when it's created, when it finishes, and when its results change (e.g. Count
every page). Reports therefore survive restarts and share links keep working. SQLite by
default (one file, no setup); Postgres in production via DATABASE_URL.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import (
    JSON,
    Column,
    Float,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
    update,
)

from app.config import settings

metadata = MetaData()
audits_table = Table(
    "audits", metadata,
    Column("id", String(32), primary_key=True),
    Column("input_url", Text, nullable=False),
    Column("host", String(255), index=True),
    Column("status", String(16), nullable=False),
    Column("created_at", Float, nullable=False, index=True),
    Column("error", Text),
    Column("events", JSON),
    Column("result", JSON),
)
# One row per audit, for the public-demo limits: who started it (salted IP hash) and what Claude cost.
usage_table = Table(
    "usage", metadata,
    Column("audit_id", String(32), primary_key=True),
    Column("visitor", String(32), index=True),
    Column("created_at", Float, nullable=False, index=True),
    Column("claude_cost", Float),  # None until the audit finishes
)
monitors_table = Table(
    "monitors", metadata,
    Column("id", String(32), primary_key=True),
    Column("url", Text, nullable=False),
    Column("host", String(255), index=True),
    Column("every_hours", Float, nullable=False),
    Column("next_run_at", Float, nullable=False),
    Column("last_audit_id", String(32)),
    Column("webhook_url", Text),
    Column("created_at", Float, nullable=False),
)


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


@dataclass
class AuditRecord:
    id: str
    input_url: str
    status: str = "queued"  # queued | running | done | error
    created_at: float = field(default_factory=time.time)
    events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    _changed: asyncio.Condition = field(default_factory=asyncio.Condition, repr=False)

    async def emit(self, event: dict[str, Any]) -> None:
        async with self._changed:
            self.events.append({"seq": len(self.events), "t": round(time.time(), 3), **event})
            self._changed.notify_all()

    async def wait_for(self, seq: int, timeout: float = 15.0) -> bool:
        """Wait until there's an event with index >= seq. Returns False on timeout."""
        async with self._changed:
            if len(self.events) > seq:
                return True
            try:
                await asyncio.wait_for(self._changed.wait_for(lambda: len(self.events) > seq), timeout)
                return True
            except TimeoutError:
                return False

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "input_url": self.input_url,
            "status": self.status,
            "created_at": self.created_at,
            "error": self.error,
            "result": self.result,
            "events": self.events,
        }


class Store:
    def __init__(self, url: str | None = None) -> None:
        self._live: dict[str, AuditRecord] = {}
        self.engine = create_engine(url or settings.database_url, future=True)
        metadata.create_all(self.engine)
        # Audits that were mid-run when the process stopped can't resume.
        with self.engine.begin() as conn:
            conn.execute(update(audits_table).where(audits_table.c.status.in_(["queued", "running"]))
                         .values(status="error", error="Interrupted by a server restart. Run the audit again."))

    # --- audits ---------------------------------------------------------------

    def create(self, input_url: str, visitor: str | None = None) -> AuditRecord:
        rec = AuditRecord(id=secrets.token_urlsafe(9), input_url=input_url)
        self._live[rec.id] = rec
        with self.engine.begin() as conn:
            conn.execute(audits_table.insert().values(
                id=rec.id, input_url=input_url, host=host_of(input_url), status=rec.status,
                created_at=rec.created_at, error=None, events=[], result={}))
            conn.execute(usage_table.insert().values(audit_id=rec.id, visitor=visitor, created_at=rec.created_at, claude_cost=None))
        return rec

    def audits_since(self, visitor: str, since: float) -> int:
        with self.engine.connect() as conn:
            return conn.execute(select(func.count()).select_from(usage_table)
                                .where(usage_table.c.visitor == visitor, usage_table.c.created_at >= since)).scalar_one()

    def claude_spend_since(self, since: float, reserve_per_running: float) -> float:
        """Claude cost of finished audits since `since`, plus the worst case for ones still running."""
        with self.engine.connect() as conn:
            rows = conn.execute(select(usage_table.c.claude_cost).where(usage_table.c.created_at >= since)).all()
        return sum(c if c is not None else reserve_per_running for (c,) in rows)

    def save(self, rec: AuditRecord) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(audits_table).where(audits_table.c.id == rec.id).values(
                status=rec.status, error=rec.error, events=rec.events, result=rec.result))
            if rec.status in ("done", "error"):
                conn.execute(update(usage_table).where(usage_table.c.audit_id == rec.id).values(
                    claude_cost=float((rec.result.get("claude") or {}).get("spent") or 0)))

    def get(self, audit_id: str) -> AuditRecord | None:
        if audit_id in self._live:
            return self._live[audit_id]
        with self.engine.connect() as conn:
            row = conn.execute(select(audits_table).where(audits_table.c.id == audit_id)).mappings().first()
        if not row:
            return None
        rec = AuditRecord(id=row["id"], input_url=row["input_url"], status=row["status"],
                          created_at=row["created_at"], events=row["events"] or [], result=row["result"] or {},
                          error=row["error"])
        self._live[rec.id] = rec  # keep it warm for follow-up requests
        return rec

    def finished(self, audit_id: str) -> None:
        """Drop a finished audit from memory once saved; it reloads from the database on demand."""
        rec = self._live.get(audit_id)
        if rec and rec.status in ("done", "error"):
            self.save(rec)

    def history(self, host: str, limit: int = 10, exclude: str | None = None) -> list[dict]:
        """Finished audits of the same site, newest first (summary fields only)."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(audits_table.c.id, audits_table.c.created_at, audits_table.c.status, audits_table.c.result)
                .where(audits_table.c.host == host, audits_table.c.status == "done")
                .order_by(audits_table.c.created_at.desc()).limit(limit + 1)
            ).mappings().all()
        out = []
        for r in rows:
            if r["id"] == exclude:
                continue
            res = r["result"] or {}
            out.append({"id": r["id"], "created_at": r["created_at"], "scores": res.get("scores"),
                        "geo": (res.get("geo") or {}).get("score"), "result": res})
        return out[:limit]

    # --- monitors ---------------------------------------------------------------

    def add_monitor(self, url: str, every_hours: float, webhook_url: str | None) -> dict:
        now = time.time()
        row = {"id": secrets.token_urlsafe(9), "url": url, "host": host_of(url), "every_hours": every_hours,
               "next_run_at": now + every_hours * 3600, "last_audit_id": None, "webhook_url": webhook_url, "created_at": now}
        with self.engine.begin() as conn:
            conn.execute(monitors_table.insert().values(**row))
        return row

    def monitors(self, host: str | None = None) -> list[dict]:
        q = select(monitors_table)
        if host:
            q = q.where(monitors_table.c.host == host)
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(q).mappings().all()]

    def due_monitors(self, now: float) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(monitors_table).where(monitors_table.c.next_run_at <= now)).mappings().all()]

    def monitor_ran(self, monitor_id: str, audit_id: str, next_run_at: float) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(monitors_table).where(monitors_table.c.id == monitor_id)
                         .values(last_audit_id=audit_id, next_run_at=next_run_at))

    def delete_monitor(self, monitor_id: str) -> bool:
        with self.engine.begin() as conn:
            return conn.execute(monitors_table.delete().where(monitors_table.c.id == monitor_id)).rowcount > 0


store = Store()
