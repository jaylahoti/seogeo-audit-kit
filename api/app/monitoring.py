"""Monitoring (module 10): compare each audit with the site's previous one, and re-audit
on a schedule.

Changes flagged per page type (matched by URL pattern): score drops of 5+ points, new high
or medium findings, and fixed findings. Site-wide: GEO and visibility changes, newly
blocked AI bots, a lost llms.txt. Scheduled monitors run in a background loop; when a
run finds regressions and the monitor has a webhook (Slack-compatible), a short message
is posted to it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from urllib.parse import urlsplit

import httpx

from app.net.safe_fetch import BlockedURL, FetchError, check_url, resolve_public
from app.store import store

log = logging.getLogger(__name__)
SCORE_DROP = 5
CHECK_EVERY_S = 60


def compare(current: dict, previous: dict) -> list[dict]:
    changes: list[dict] = []

    def add(severity: str, kind: str, title: str, detail: str = "", pages: int = 0, page_type: str | None = None):
        changes.append({"severity": severity, "kind": kind, "title": title, "detail": detail, "pages": pages, "page_type": page_type})

    prev_t = {t["pattern"]: t for t in previous.get("templates", [])}
    for t in current.get("templates", []):
        p = prev_t.get(t["pattern"])
        if not p:
            continue
        for key, label in (("seo_score", "SEO"), ("ai_score", "AI readiness")):
            a, b = p.get(key), t.get(key)
            if a is not None and b is not None and a - b >= SCORE_DROP:
                add("high" if a - b >= 15 else "medium", "regression", f"{label} dropped {a} → {b} on {t['pattern']}",
                    pages=t["estimated_pages"], page_type=t["pattern"])
        old = {f["id"] for f in p.get("findings", [])}
        new = {f["id"] for f in t.get("findings", [])}
        for f in t.get("findings", []):
            if f["id"] not in old and f["severity"] in ("high", "medium"):
                add(f["severity"], "new_issue", f"New on {t['pattern']}: {f['title']}", f["detail"], f["pages"], t["pattern"])
        for f in p.get("findings", []):
            if f["id"] not in new and f["severity"] in ("high", "medium"):
                add("low", "fixed", f"Fixed on {t['pattern']}: {f['title']}", pages=t["estimated_pages"], page_type=t["pattern"])

    def score(r: dict, *path):
        v = r
        for k in path:
            v = (v or {}).get(k)
        return v

    for path, label in ((("geo", "score"), "GEO score"), (("visibility", "score"), "AI visibility")):
        a, b = score(previous, *path), score(current, *path)
        if a is not None and b is not None and a - b >= SCORE_DROP:
            add("high" if a - b >= 15 else "medium", "regression", f"{label} dropped {a} → {b}")

    before = set(score(previous, "robots", "blocked_retrieval_bots") or [])
    after = set(score(current, "robots", "blocked_retrieval_bots") or [])
    for bot in sorted(after - before):
        add("high", "new_issue", f"robots.txt now blocks {bot}", "A retrieval bot was blocked since the last audit.")
    if score(previous, "llms_txt", "found") and not score(current, "llms_txt", "found"):
        add("medium", "new_issue", "llms.txt disappeared")

    order = {"high": 0, "medium": 1, "low": 2}
    changes.sort(key=lambda c: (order[c["severity"]], -c["pages"]))
    return changes


def attach(rec_id: str, host: str, result: dict) -> None:
    """Add the comparison with the previous audit and the score history to `result`."""
    history = store.history(host, limit=10, exclude=rec_id)
    trend = [{"id": h["id"], "at": h["created_at"], "seo": (h["scores"] or {}).get("seo"),
              "ai": (h["scores"] or {}).get("ai"), "geo": h["geo"]} for h in reversed(history)]
    trend.append({"id": rec_id, "at": time.time(), "seo": (result.get("scores") or {}).get("seo"),
                  "ai": (result.get("scores") or {}).get("ai"), "geo": (result.get("geo") or {}).get("score")})
    prev = history[0] if history else None
    result["monitoring"] = {
        "previous_id": prev["id"] if prev else None,
        "previous_at": prev["created_at"] if prev else None,
        "changes": compare(result, prev["result"]) if prev else [],
        "trend": trend,
        "monitors": [{k: m[k] for k in ("id", "every_hours", "next_run_at")} for m in store.monitors(host)],
    }


async def notify(webhook_url: str, site: str, audit_id: str, changes: list[dict]) -> None:
    bad = [c for c in changes if c["severity"] in ("high", "medium") and c["kind"] != "fixed"]
    if not bad:
        return
    try:
        check_url(webhook_url)
        await resolve_public(urlsplit(webhook_url).hostname or "")
    except (BlockedURL, FetchError):
        return  # never post to internal addresses
    lines = "\n".join(f"• [{c['severity']}] {c['title']}" for c in bad[:8])
    with contextlib.suppress(httpx.HTTPError):
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            await client.post(webhook_url, json={"text": f"SEOGEO Audit Kit: {len(bad)} regression(s) on {site} (audit {audit_id})\n{lines}"})


async def scheduler(start_audit) -> None:
    """Run due monitors forever. `start_audit(url) -> AuditRecord` starts and returns an audit."""
    while True:
        try:
            for m in store.due_monitors(time.time()):
                store.monitor_ran(m["id"], m["last_audit_id"] or "", time.time() + m["every_hours"] * 3600)
                rec = await start_audit(m["url"])
                store.monitor_ran(m["id"], rec.id, time.time() + m["every_hours"] * 3600)
                if m.get("webhook_url"):
                    asyncio.create_task(_notify_when_done(rec, m))
        except Exception:  # keep the loop alive; one bad monitor mustn't stop the rest
            log.exception("Scheduled audit failed")
        await asyncio.sleep(CHECK_EVERY_S)


async def _notify_when_done(rec, monitor: dict) -> None:
    while rec.status not in ("done", "error"):
        await asyncio.sleep(5)
    if rec.status == "done":
        await notify(monitor["webhook_url"], monitor["host"], rec.id, (rec.result.get("monitoring") or {}).get("changes", []))
