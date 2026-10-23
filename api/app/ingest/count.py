"""Exact page count: read every sitemap file and count URLs, without re-running the audit.

The audit samples a fair share of sitemap files (smart sampling). When the exact number
matters, this reads all of them — following nested indexes — and counts URLs per sitemap
family and per template. URLs are counted as they're parsed and not kept, so memory stays
flat even for millions of pages. Counts are of URL entries; the same URL listed in two
files is counted twice (rare, and deduplicating would mean holding every URL in memory).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from app.checks.links import pattern_regex
from app.config import settings
from app.ingest.sitemap import SitemapResult, _fetch_sitemap, _same_site, family

CONCURRENCY = 4


@dataclass
class ExactCount:
    status: str = "running"  # running | done | error
    files_total: int = 0  # URL-list files found so far (grows while indexes are expanded)
    files_done: int = 0
    files_failed: int = 0
    urls: int = 0
    families: dict[str, dict] = field(default_factory=dict)  # family -> {files, urls}
    templates: dict[str, int] = field(default_factory=dict)  # URL pattern -> URLs
    unmatched: int = 0
    error: str | None = None


def classifier(patterns: list[str]) -> Callable[[str], str | None]:
    compiled = [(p, rx) for p in dict.fromkeys(patterns) if (rx := pattern_regex(p)) is not None]
    path_rx = re.compile(r"^https?://[^/]+(/[^?#]*)?")

    def classify(url: str) -> str | None:
        m = path_rx.match(url)
        path = (m.group(1) if m else None) or "/"
        for pattern, rx in compiled:
            if rx.match(path):
                return pattern
        return None

    return classify


async def count_all(
    client: httpx.AsyncClient,
    start: list[str],
    patterns: list[str],
    state: ExactCount,
    on_progress: Callable[[ExactCount], Awaitable[None]] | None = None,
) -> ExactCount:
    classify = classifier(patterns)
    scratch = SitemapResult()  # collects fetch issues; we only report counts
    site = start[0] if start else ""
    seen: set[str] = set()
    queue: asyncio.Queue[str] = asyncio.Queue()
    for s in dict.fromkeys(start):
        seen.add(s)
        queue.put_nowait(s)

    async def handle(sm: str):
        parsed = await _fetch_sitemap(client, sm, scratch)
        if not parsed:
            state.files_failed += 1
            return
        kind, entries = parsed
        if kind == "index":
            for e in entries:
                if e.loc not in seen:
                    if len(seen) >= settings.max_count_files:
                        raise RuntimeError(
                            f"More than {settings.max_count_files:,} sitemap files — raise MAX_COUNT_FILES to count them all."
                        )
                    seen.add(e.loc)
                    queue.put_nowait(e.loc)
            return
        state.files_total += 1
        fam = state.families.setdefault(family(sm), {"files": 0, "urls": 0})
        fam["files"] += 1
        n = 0
        for e in entries:
            if not _same_site(e.loc, site):
                continue
            n += 1
            t = classify(e.loc)
            if t is None:
                state.unmatched += 1
            else:
                state.templates[t] = state.templates.get(t, 0) + 1
        fam["urls"] += n
        state.urls += n
        state.files_done += 1
        if on_progress:
            await on_progress(state)

    async def worker():
        while True:
            try:
                sm = queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            await handle(sm)

    # Workers stop when the queue is empty; indexes add work, so loop until nothing is left.
    try:
        while not queue.empty():
            await asyncio.gather(*(worker() for _ in range(CONCURRENCY)))
        state.status = "done"
    except RuntimeError as e:
        state.status, state.error = "error", str(e)
    return state
