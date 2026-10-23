"""Link checks: click depth per template, broken internal links, links to redirects.

Depth is measured with a small breadth-first crawl from the home page (bounded pages and
depth), so it shows how reachable each template is through navigation rather than only
through the sitemap. Broken links are found by fetching a sample of link targets seen on
crawled pages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

from app.checks.page_facts import PageFacts, extract
from app.crawl.crawler import crawl
from app.ingest.robots import RobotsInfo

MAX_DEPTH = 3
MAX_BFS_PAGES = 60
MAX_LINK_PROBES = 40


def pattern_regex(pattern: str) -> re.Pattern | None:
    if pattern == "/{static}":
        return None
    if pattern == "/":
        return re.compile(r"^/?$")
    parts = []
    for seg in pattern.strip("/").split("/"):
        parts.append("[^/]+" if seg.startswith("{") else re.escape(seg))
    return re.compile("^/" + "/".join(parts) + "/?$")


def template_of(url: str, regexes: list[tuple[str, re.Pattern | None]]) -> str | None:
    path = urlsplit(url).path or "/"
    for pattern, rx in regexes:
        if rx is not None and rx.match(path):
            return pattern
    return None


@dataclass
class LinkReport:
    depth: dict[str, int | None] = field(default_factory=dict)  # template -> min clicks from home
    inbound: dict[str, int] = field(default_factory=dict)  # template -> links seen pointing at it
    bfs_pages: int = 0
    probed: int = 0
    broken: list[dict] = field(default_factory=list)  # {target, status, found_on}
    redirecting: list[dict] = field(default_factory=list)  # {target, to, hops, found_on}
    home: PageFacts | None = None  # the home page, used by the llms.txt generator


async def check_links(
    client: httpx.AsyncClient,
    robots: RobotsInfo,
    home: str,
    patterns: list[str],
    crawled: list[PageFacts],
) -> LinkReport:
    regexes = [(p, pattern_regex(p)) for p in patterns]
    report = LinkReport(depth={p: None for p in patterns}, inbound={p: 0 for p in patterns})
    seen: dict[str, PageFacts] = {}
    found_on: dict[str, str] = {}

    def record(facts: PageFacts, depth: int):
        own = template_of(facts.final_url, regexes)
        if own and (report.depth[own] is None or depth < report.depth[own]):
            report.depth[own] = depth
        for link in facts.internal_links:
            found_on.setdefault(link, facts.url)
            t = template_of(link, regexes)
            if t:
                report.inbound[t] += 1
                if report.depth[t] is None or depth + 1 < report.depth[t]:
                    report.depth[t] = depth + 1

    # Breadth-first from the home page, preferring links into templates not yet reached.
    frontier = [home.rstrip("/") + "/"]
    for depth in range(MAX_DEPTH):
        budget = MAX_BFS_PAGES - len(seen)
        if budget <= 0 or not frontier:
            break
        pages = await crawl(client, frontier[:budget], robots)
        next_links: list[str] = []
        for page in pages:
            facts = extract(page)
            seen[page.url] = facts
            if depth == 0 and page.ok_html:
                report.home = facts
            if page.ok_html:
                record(facts, depth)
                next_links.extend(facts.internal_links)
        frontier = _diverse(next_links, set(seen), regexes, report, limit=MAX_BFS_PAGES - len(seen))
    report.bfs_pages = len(seen)

    # Links seen on the audit's sample pages count too (they're one click from those pages).
    for facts in crawled:
        for link in facts.internal_links:
            found_on.setdefault(link, facts.url)

    # Probe link targets we haven't fetched, spread across templates.
    fetched = {f.url.rstrip("/") for f in crawled} | {u.rstrip("/") for u in seen}
    targets = [t for t in dict.fromkeys(found_on) if t.rstrip("/") not in fetched]
    targets = _diverse(targets, set(), regexes, None, limit=MAX_LINK_PROBES)
    report.probed = len(targets)
    for page in await crawl(client, targets, robots):
        if page.blocked_by_robots:
            continue
        if page.status and page.status >= 400:
            report.broken.append({"target": page.url, "status": page.status, "found_on": found_on.get(page.url)})
        elif page.redirects:
            report.redirecting.append({
                "target": page.url, "to": page.final_url, "hops": len(page.redirects),
                "found_on": found_on.get(page.url),
            })
    # Redirects already observed while crawling count as well.
    for facts in [*crawled, *seen.values()]:
        if len(facts.redirects) > 1:
            report.redirecting.append({"target": facts.url, "to": facts.final_url, "hops": len(facts.redirects), "found_on": found_on.get(facts.url)})
    return report


def _diverse(links: list[str], skip: set[str], regexes, report: LinkReport | None, limit: int) -> list[str]:
    """Round-robin links across templates (unreached templates first) so a bounded crawl covers the site."""
    if limit <= 0:
        return []
    groups: dict[str, list[str]] = {}
    for link in dict.fromkeys(links):
        if link in skip or link.rstrip("/") in skip:
            continue
        groups.setdefault(template_of(link, regexes) or "?", []).append(link)
    order = sorted(groups, key=lambda t: (report is not None and report.depth.get(t) is not None, t))
    out: list[str] = []
    i = 0
    while len(out) < limit and any(i < len(groups[t]) for t in order):
        for t in order:
            if i < len(groups[t]) and len(out) < limit:
                out.append(groups[t][i])
        i += 1
    return out
