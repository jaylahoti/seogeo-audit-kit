"""Check one page: every SEO and AI-readiness check, plus Claude's page check if a key is set.

Used by the CLI (`seogeo-audit page <url>`) and the MCP server's `check_page` tool — handy
right after fixing a page, without running a whole-site audit.
"""

from __future__ import annotations

from dataclasses import asdict

from app.checks import ai as ai_checks
from app.checks import seo as seo_checks
from app.checks.findings import TemplateContext, score
from app.checks.page_facts import extract
from app.crawl.crawler import crawl
from app.ingest.robots import fetch_robots
from app.llm import page_checks
from app.llm.client import Claude
from app.net.safe_fetch import check_url, make_client


async def check_page(url: str) -> dict:
    if "://" not in url:
        url = f"https://{url}"
    check_url(url)
    async with make_client() as client:
        robots = await fetch_robots(client, url)
        (page,) = await crawl(client, [url], robots)
    if page.blocked_by_robots:
        return {"url": url, "error": "robots.txt disallows this page for SEOGEOAuditKitBot"}
    if page.error or page.status is None:
        return {"url": url, "error": page.error or "Couldn't fetch the page"}
    facts = extract(page)
    ctx = TemplateContext(pattern=url, estimated_pages=1, samples=[facts], lastmods={})
    # Sitemap checks need the sitemap; a single URL has none.
    findings = [f for f in seo_checks.run(ctx) + ai_checks.run(ctx) if not f.id.startswith("lastmod_")]
    claude = Claude(budget=0.02)
    claude_check = None
    if claude.enabled and page.status == 200:
        res = await page_checks.check_pages(claude, [(url, facts)])
        if res.get(url):
            claude_check = page_checks.summarize(res[url])
            findings = [f for f in findings if f.id not in ("no_verdict", "facts_buried")]
            findings += page_checks.findings(ctx, res[url], [facts])
    return {
        "url": url,
        "status": page.status,
        "title": facts.title,
        "words": facts.word_count,
        "schema_types": sorted({t for b in facts.jsonld if b.data is not None for e in ai_checks.entities(b.data) for t in ai_checks._types(e)}),
        "seo_score": score(findings, "seo"),
        "ai_score": score(findings, "ai"),
        "findings": [{k: v for k, v in asdict(f).items() if k not in ("affected", "sampled", "pages")} for f in findings],
        "claude": claude_check,
        "cost_usd": round(claude.ledger.spent, 5),
    }
