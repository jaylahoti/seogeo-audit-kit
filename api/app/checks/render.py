"""Module 7 — what AI sees: the page as raw HTML (how most AI crawlers read it) vs rendered.

GPTBot, ClaudeBot, PerplexityBot and most other AI crawlers don't run JavaScript, so
content that only appears after JS runs is invisible to them. Each template's sample is
rendered in headless Chromium and compared with the raw HTML the crawler already fetched.

Rendering an untrusted page means running its JavaScript on our server, so every request
the browser makes is routed through the same public-address check as safe_fetch, and
private, loopback and metadata addresses are refused. Limitation: Chromium resolves DNS
itself, so the check and the connection use separate lookups; requests are additionally
limited to http(s), and service workers and downloads are disabled.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.checks.findings import Finding
from app.checks.page_facts import PageFacts, extract
from app.config import settings
from app.crawl.crawler import Page
from app.ingest.robots import RobotsInfo
from app.net.safe_fetch import BlockedURL, FetchError, resolve_public

SKIP_RESOURCES = {"image", "media", "font"}
RENDER_TIMEOUT_MS = 20_000
CONCURRENCY = 3


@dataclass
class RenderDiff:
    url: str
    raw_words: int
    rendered_words: int
    raw_links: int
    rendered_links: int
    raw_jsonld: int
    rendered_jsonld: int
    js_only_headings: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def js_text_share(self) -> float:
        if self.rendered_words <= 0:
            return 0.0
        return max(0.0, 1 - self.raw_words / self.rendered_words)


async def render_html(urls: list[str], robots: RobotsInfo) -> dict[str, str | None]:
    """Render each URL in headless Chromium. Returns url -> rendered HTML (None on failure)."""
    from playwright.async_api import async_playwright  # heavy import, only when rendering

    allowed_hosts: dict[str, bool] = {}

    async def guard(route):
        req = route.request
        if req.resource_type in SKIP_RESOURCES:
            return await route.abort()
        parts = urlsplit(req.url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            return await route.abort()
        host = parts.hostname
        if host not in allowed_hosts:
            try:
                await resolve_public(host)
                allowed_hosts[host] = True
            except (BlockedURL, FetchError):
                allowed_hosts[host] = False
        if not allowed_hosts[host]:
            return await route.abort("blockedbyclient")
        return await route.continue_()

    results: dict[str, str | None] = {}
    sem = asyncio.Semaphore(CONCURRENCY)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=f"{settings.user_agent} rendering",
            service_workers="block",
            accept_downloads=False,
        )
        await context.route("**/*", guard)

        async def one(url: str):
            if not robots.can_fetch(url):
                results[url] = None
                return
            async with sem:
                page = await context.new_page()
                try:
                    try:
                        await page.goto(url, wait_until="networkidle", timeout=RENDER_TIMEOUT_MS)
                    except Exception:  # noqa: BLE001 — pages that never go idle: use what loaded
                        await page.wait_for_load_state("load", timeout=5_000)
                    results[url] = await page.content()
                except Exception:  # noqa: BLE001 — a page that can't render is reported, not fatal
                    results[url] = None
                finally:
                    await page.close()

        await asyncio.gather(*(one(u) for u in urls))
        await browser.close()
    return results


def compare(raw: PageFacts, rendered_html: str | None) -> RenderDiff:
    if rendered_html is None:
        return RenderDiff(raw.url, raw.word_count, 0, len(raw.internal_links), 0, len(raw.jsonld), 0, error="Couldn't render")
    rendered = extract(Page(url=raw.url, final_url=raw.final_url, status=200, content_type="text/html", html=rendered_html))
    raw_heads = {t.lower() for _, t in raw.headings}
    js_only = [t for _, t in rendered.headings if t.lower() not in raw_heads][:6]
    return RenderDiff(
        url=raw.url,
        raw_words=raw.word_count,
        rendered_words=rendered.word_count,
        raw_links=len(raw.internal_links),
        rendered_links=len(rendered.internal_links),
        raw_jsonld=sum(1 for b in raw.jsonld if b.data is not None),
        rendered_jsonld=sum(1 for b in rendered.jsonld if b.data is not None),
        js_only_headings=js_only,
    )


def findings(diff: RenderDiff, estimated_pages: int) -> list[Finding]:
    out: list[Finding] = []

    def add(id_: str, severity: str, title: str, detail: str):
        out.append(Finding(id=id_, area="ai", severity=severity, title=title, detail=detail,
                           affected=1, sampled=1, pages=estimated_pages, examples=[diff.url], method="render"))

    if diff.error:
        return out
    share = diff.js_text_share
    if share >= 0.2:
        heads = f" Sections only there after JS: {', '.join(diff.js_only_headings)}." if diff.js_only_headings else ""
        add("js_text", "high" if share >= 0.5 else "medium",
            f"{share:.0%} of the text needs JavaScript",
            f"Raw HTML has {diff.raw_words:,} words; the rendered page has {diff.rendered_words:,}. "
            f"Most AI crawlers only see the raw HTML.{heads} Server-render these sections.")
    if diff.rendered_jsonld > diff.raw_jsonld and diff.raw_jsonld == 0:
        add("js_jsonld", "high", "JSON-LD is added by JavaScript",
            "Structured data only appears after scripts run, so crawlers that don't run JavaScript never see it. Render it in the HTML.")
    if diff.rendered_links - diff.raw_links >= 10 and diff.rendered_links > diff.raw_links * 1.5:
        add("js_links", "medium", "Internal links need JavaScript",
            f"{diff.raw_links} links in raw HTML vs {diff.rendered_links} after rendering. Crawlers that don't run JS can't follow the rest.")
    return out
