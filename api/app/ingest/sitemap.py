"""Sitemap ingest: follows sitemap indexes, handles gzip, caps the URL count."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx
from defusedxml import ElementTree as ET  # guards against XML bombs

from app.config import settings
from app.net.safe_fetch import BlockedURL, FetchError, safe_get


@dataclass
class SitemapURL:
    loc: str
    lastmod: str | None = None
    # How many real URLs this sampled URL stands for (sitemap size / URLs kept from it).
    weight: float = 1.0


@dataclass
class SitemapIssue:
    sitemap: str
    message: str


@dataclass
class SitemapResult:
    urls: list[SitemapURL] = field(default_factory=list)
    sitemaps_read: list[str] = field(default_factory=list)
    issues: list[SitemapIssue] = field(default_factory=list)
    truncated: bool = False  # True when we sampled instead of reading everything
    off_host: int = 0  # URLs pointing at another host, skipped
    listed_total: int = 0  # URLs listed across every sitemap we read

    @property
    def estimated_total(self) -> int:
        return round(sum(u.weight for u in self.urls))


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_sitemap_xml(body: bytes) -> tuple[str, list[SitemapURL]]:
    """Return ("index" | "urlset", entries). Raises ValueError on malformed XML."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        raise ValueError(f"Not valid XML: {e}") from e
    kind = _local(root.tag)
    if kind not in ("sitemapindex", "urlset"):
        raise ValueError(f"Unexpected root element <{kind}>")
    child = "sitemap" if kind == "sitemapindex" else "url"
    entries: list[SitemapURL] = []
    for node in root:
        if _local(node.tag) != child:
            continue
        loc = lastmod = None
        for field_ in node:
            name = _local(field_.tag)
            if name == "loc" and field_.text:
                loc = field_.text.strip()
            elif name == "lastmod" and field_.text:
                lastmod = field_.text.strip()
        if loc:
            entries.append(SitemapURL(loc=loc, lastmod=lastmod))
    return ("index" if kind == "sitemapindex" else "urlset"), entries


def _same_site(a: str, b: str) -> bool:
    ha, hb = urlsplit(a).hostname or "", urlsplit(b).hostname or ""
    strip = lambda h: h.removeprefix("www.")
    return strip(ha) == strip(hb)


async def _fetch_sitemap(client, sm: str, result: SitemapResult):
    try:
        res = await safe_get(client, sm, max_bytes=settings.max_sitemap_bytes, accept="application/xml")
    except (FetchError, BlockedURL) as e:
        result.issues.append(SitemapIssue(sm, str(e)))
        return None
    if res.status >= 400:
        result.issues.append(SitemapIssue(sm, f"Returned HTTP {res.status}"))
        return None
    try:
        parsed = parse_sitemap_xml(res.body)
    except ValueError as e:
        result.issues.append(SitemapIssue(sm, str(e)))
        return None
    result.sitemaps_read.append(sm)
    return parsed


def family(sitemap_url: str) -> str:
    """sitemap_apartments__003.xml and sitemap_apartments__017.xml are the same family."""
    return re.sub(r"\d+", "#", urlsplit(sitemap_url).path)


def pick_leaves(leaves: list[str], limit: int) -> list[str]:
    """Round-robin across families so every page type is represented.

    Within a family, files are taken in a spread order (golden-ratio stride) so the first
    few picks cover the start, middle and end of the numbered range.
    """
    groups: dict[str, list[str]] = {}
    for leaf in leaves:
        groups.setdefault(family(leaf), []).append(leaf)
    orders = [
        [g[i] for i in sorted(range(len(g)), key=lambda i: (i * 0.6180339887) % 1)]
        for g in groups.values()
    ]
    picked: list[str] = []
    rank = 0
    while len(picked) < limit and any(rank < len(o) for o in orders):
        for o in orders:
            if rank < len(o) and len(picked) < limit:
                picked.append(o[rank])
        rank += 1
    return picked


async def ingest_sitemaps(
    client: httpx.AsyncClient,
    start: list[str],
    *,
    max_urls: int | None = None,
    on_progress=None,
) -> SitemapResult:
    """Read the sitemap index fully, then sample leaf sitemaps across every family.

    Big sites split sitemaps by page type and number them (apartments__001 … __180), so
    reading the first N files or URLs would miss whole templates. Steps:
      1. Expand indexes to get every leaf sitemap (cheap: indexes are small).
      2. Pick up to max_sitemaps leaves, round-robin across name families.
      3. Give each picked leaf an equal share of the URL budget, spread through the file.
    Each kept URL carries a weight = (URLs in its file / URLs kept) × (files in its family /
    files read), so per-template page counts are estimates for the whole site.
    """
    max_urls = max_urls or settings.max_urls
    result = SitemapResult()
    site = start[0] if start else ""

    # 1. Read the start URLs. Children of an index are treated as leaves (not fetched yet);
    #    a child that turns out to be another index is expanded when it's read in step 3.
    leaves: list[str] = []
    preloaded: dict[str, list[SitemapURL]] = {}
    index_reads = 0
    for sm in dict.fromkeys(start):
        parsed = await _fetch_sitemap(client, sm, result)
        if not parsed:
            continue
        kind, entries = parsed
        if kind == "index":
            index_reads += 1
            leaves.extend(e.loc for e in entries)
        else:
            leaves.append(sm)
            preloaded[sm] = entries
    leaves = list(dict.fromkeys(leaves))

    # 2. Choose which leaves to read.
    budget_files = max(1, settings.max_sitemaps - index_reads)
    picked = pick_leaves(leaves, budget_files)
    if len(picked) < len(leaves):
        result.truncated = True
    fam_total: dict[str, int] = {}
    fam_read: dict[str, int] = {}
    for leaf in leaves:
        fam_total[family(leaf)] = fam_total.get(family(leaf), 0) + 1
    for leaf in picked:
        fam_read[family(leaf)] = fam_read.get(family(leaf), 0) + 1

    # 3. Read and sample each picked leaf.
    share = max(1, max_urls // max(1, len(picked)))
    seen_urls: set[str] = set()
    for leaf in picked:
        entries = preloaded.pop(leaf, None)
        if entries is None:
            parsed = await _fetch_sitemap(client, leaf, result)
            if not parsed:
                continue
            kind, entries = parsed
            if kind == "index":
                # Nested index: read a few of its children in its place.
                entries = await _read_nested(client, entries, result, limit=3)
        fresh = [e for e in entries if e.loc not in seen_urls]
        on_host = [e for e in fresh if _same_site(e.loc, site)]
        result.off_host += len(fresh) - len(on_host)
        result.listed_total += len(on_host)
        kept = _spread(on_host, share)
        if len(kept) < len(on_host):
            result.truncated = True
        fam = family(leaf)
        weight = (len(on_host) / len(kept) if kept else 1.0) * (fam_total[fam] / fam_read[fam])
        for e in kept:
            seen_urls.add(e.loc)
            e.weight = weight
            result.urls.append(e)
        if on_progress:
            await on_progress(len(result.urls), len(result.sitemaps_read))

    return result


async def _read_nested(client, children: list[SitemapURL], result: SitemapResult, limit: int):
    out: list[SitemapURL] = []
    for child in _spread(children, limit):
        parsed = await _fetch_sitemap(client, child.loc, result)
        if parsed and parsed[0] == "urlset":
            out.extend(parsed[1])
    return out


def _spread(items: list[SitemapURL], n: int) -> list[SitemapURL]:
    """Take n items spread evenly through the list (sitemaps are often sorted by type or date)."""
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]
