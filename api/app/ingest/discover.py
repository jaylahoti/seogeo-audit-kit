"""Find a site's URLs when it has no sitemap: try the usual sitemap paths, then follow links.

Link discovery is a bounded breadth-first crawl from the home page that collects internal
links. Every discovered URL counts once (weight 1), so page counts are "pages found", not
an estimate of the whole site.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from app.checks.page_facts import extract
from app.crawl.crawler import crawl
from app.ingest.robots import RobotsInfo
from app.ingest.sitemap import SitemapURL

COMMON_SITEMAPS = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/wp-sitemap.xml",
    "/sitemap/sitemap.xml",
    "/sitemaps/sitemap.xml",
    "/sitemap.xml.gz",
]
MAX_DISCOVERY_PAGES = 30
MAX_DISCOVERED_URLS = 2000


def candidate_sitemaps(site_url: str) -> list[str]:
    p = urlsplit(site_url)
    return [f"{p.scheme}://{p.netloc}{path}" for path in COMMON_SITEMAPS]


async def discover_by_links(client: httpx.AsyncClient, site_url: str, robots: RobotsInfo) -> list[SitemapURL]:
    p = urlsplit(site_url)
    home = f"{p.scheme}://{p.netloc}/"
    found: dict[str, None] = {home: None}
    frontier = [home]
    fetched: set[str] = set()
    while frontier and len(fetched) < MAX_DISCOVERY_PAGES and len(found) < MAX_DISCOVERED_URLS:
        batch = frontier[: MAX_DISCOVERY_PAGES - len(fetched)]
        frontier = frontier[len(batch):]
        for page in await crawl(client, batch, robots):
            fetched.add(page.url)
            if not page.ok_html:
                continue
            for link in extract(page).internal_links:
                if urlsplit(link).query or link in found:
                    continue
                found[link] = None
                frontier.append(link)
        # Visit different sections first, so a small crawl reaches more templates.
        frontier = _by_section(frontier)
    return [SitemapURL(loc=u) for u in list(found)[:MAX_DISCOVERED_URLS]]


def _by_section(links: list[str]) -> list[str]:
    groups: dict[str, list[str]] = {}
    for link in links:
        first = (urlsplit(link).path.strip("/").split("/") or [""])[0]
        groups.setdefault(first, []).append(link)
    out: list[str] = []
    i = 0
    while any(i < len(g) for g in groups.values()):
        for g in groups.values():
            if i < len(g):
                out.append(g[i])
        i += 1
    return out
