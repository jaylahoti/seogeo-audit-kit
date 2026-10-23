"""Polite page crawler: robots.txt + Crawl-delay respected, per-host concurrency capped."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.ingest.robots import RobotsInfo
from app.net.safe_fetch import BlockedURL, FetchError, safe_get

MAX_CRAWL_DELAY_S = 2.0  # honour Crawl-delay up to this; beyond it we crawl fewer pages instead
PER_HOST_CONCURRENCY = 4
MIN_INTERVAL_S = 0.15  # floor between request starts to one host


@dataclass
class Page:
    url: str  # the URL we asked for (from the sitemap)
    final_url: str = ""
    status: int | None = None
    content_type: str = ""
    html: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    redirects: list[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    error: str | None = None
    blocked_by_robots: bool = False

    @property
    def ok_html(self) -> bool:
        return self.status == 200 and "html" in self.content_type and bool(self.html)


class _HostPacer:
    """Spaces out request starts so we never hammer one host."""

    def __init__(self, interval: float):
        self.interval = interval
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self):
        async with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            await asyncio.sleep(delay)


async def crawl(
    client: httpx.AsyncClient,
    urls: list[str],
    robots: RobotsInfo,
    *,
    on_page=None,
) -> list[Page]:
    crawl_delay = 0.0
    if robots._parser:
        crawl_delay = float(robots._parser.crawl_delay(settings.user_agent) or 0)
    interval = max(MIN_INTERVAL_S, min(crawl_delay, MAX_CRAWL_DELAY_S))
    concurrency = 1 if crawl_delay else PER_HOST_CONCURRENCY
    pacer = _HostPacer(interval)
    sem = asyncio.Semaphore(concurrency)

    async def one(url: str) -> Page:
        page = Page(url=url)
        if not robots.can_fetch(url):
            page.blocked_by_robots = True
            page.error = "Disallowed by robots.txt"
            return page
        async with sem:
            await pacer.wait()
            try:
                res = await safe_get(client, url, accept="text/html,application/xhtml+xml")
            except (FetchError, BlockedURL) as e:
                page.error = str(e)
                return page
        page.final_url = res.url
        page.status = res.status
        page.headers = res.headers
        page.content_type = res.headers.get("content-type", "")
        page.redirects = res.redirects
        page.elapsed_ms = res.elapsed_ms
        if "html" in page.content_type:
            page.html = res.text()
        if on_page:
            await on_page(page)
        return page

    return await asyncio.gather(*(one(u) for u in urls))
