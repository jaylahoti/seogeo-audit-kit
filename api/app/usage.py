"""Public-demo limits: free audits per visitor per day, and a daily Claude budget for the whole site.

Visitors are identified by a salted hash of their IP (the IP itself is never stored). Requests
from this machine are never limited, so local development and self-hosting on a laptop just work.
When the daily budget is used up, audits still run, on rules, ML and the browser only.
"""

from __future__ import annotations

import hashlib
import ipaddress
import time

from fastapi import HTTPException, Request

from app.config import settings
from app.store import store

DAY = 86400
REPO = "https://github.com/jaylahoti/seogeo-audit-kit"


def client_ip(request: Request) -> str:
    """The visitor's IP. Behind a proxy, the left of X-Forwarded-For is whatever the client sent
    (spoofable), so use the proxy's own header (Fly) or the entry the proxy appended (the last one)."""
    if settings.trust_proxy:
        fly = request.headers.get("fly-client-ip", "").strip()
        if fly:
            return fly
        fwd = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if fwd:
            return fwd[-1]
    return request.client.host if request.client else ""


def is_local(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return ip in ("localhost", "testclient")


def visitor_id(ip: str) -> str:
    return hashlib.sha256(f"{settings.visitor_salt}:{ip}".encode()).hexdigest()[:24]


def check_visitor(request: Request) -> str | None:
    """Returns the visitor id to record, or None for local requests. Raises 429 when over the limit."""
    ip = client_ip(request)
    if is_local(ip):
        return None
    vid = visitor_id(ip)
    limit = settings.free_audits_per_day
    if limit and store.audits_since(vid, time.time() - DAY) >= limit:
        raise HTTPException(status_code=429, detail=(
            f"You've used your {limit} free audits for today. More are available 24 hours after your first one, "
            f"or self-host it for unlimited audits: {REPO}"))
    return vid


def claude_allowed() -> bool:
    """False when today's Claude spend (plus the worst case for audits still running) reaches the cap."""
    cap = settings.daily_budget_usd
    if not cap:
        return True
    spent = store.claude_spend_since(time.time() - DAY, reserve_per_running=settings.max_audit_cost_usd)
    return spent + settings.max_audit_cost_usd <= cap
