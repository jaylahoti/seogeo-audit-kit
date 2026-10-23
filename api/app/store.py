"""Audit storage. In-memory for now, behind a small interface so Postgres can replace it."""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Any


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


class MemoryStore:
    def __init__(self) -> None:
        self._audits: dict[str, AuditRecord] = {}

    def create(self, input_url: str) -> AuditRecord:
        rec = AuditRecord(id=secrets.token_urlsafe(9), input_url=input_url)
        self._audits[rec.id] = rec
        return rec

    def get(self, audit_id: str) -> AuditRecord | None:
        return self._audits.get(audit_id)


store = MemoryStore()
