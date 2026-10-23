"""/llms.txt check, following the llmstxt.org format.

Expected shape: one H1 (site name), a > blockquote summary, optional prose, then H2
sections of markdown links to the pages worth retrieving.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import httpx

from app.net.safe_fetch import BlockedURL, FetchError, safe_get

RE_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
RE_INTERNAL_HOST = re.compile(r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|[^/]*\.local)(:\d+)?(/|$)", re.IGNORECASE)


@dataclass
class LlmsTxtCheck:
    url: str
    found: bool
    status: int | None = None
    bytes: int = 0
    title: str | None = None
    has_summary: bool = False
    sections: list[str] = field(default_factory=list)
    links: int = 0
    off_site_links: int = 0
    internal_host_links: list[str] = field(default_factory=list)
    mentions_sitemap: bool = False
    has_full_version: bool = False  # /llms-full.txt
    issues: list[str] = field(default_factory=list)


def analyse(url: str, text: str) -> LlmsTxtCheck:
    check = LlmsTxtCheck(url=url, found=True, bytes=len(text.encode()))
    lines = text.splitlines()
    h1 = [ln[2:].strip() for ln in lines if ln.startswith("# ")]
    check.title = h1[0] if h1 else None
    check.has_summary = any(ln.startswith(">") for ln in lines)
    check.sections = [ln[3:].strip() for ln in lines if ln.startswith("## ")]

    host = (urlsplit(url).hostname or "").removeprefix("www.")
    links = RE_LINK.findall(text)
    check.links = len(links)
    check.off_site_links = sum(
        1 for _, href in links if (urlsplit(href).hostname or "").removeprefix("www.") != host
    )
    check.internal_host_links = sorted({m.group(0) for m in RE_INTERNAL_HOST.finditer(text)})[:5]
    check.mentions_sitemap = "sitemap" in text.lower()

    if len(h1) != 1:
        check.issues.append("Should start with exactly one H1 naming the site")
    if not check.has_summary:
        check.issues.append("No > blockquote summary of what the site is")
    if not check.sections:
        check.issues.append("No ## sections grouping the important pages")
    if check.links == 0:
        check.issues.append("No markdown links to pages")
    if check.internal_host_links:
        check.issues.append("Links to localhost or internal hosts")
    if "## Optional" in text:
        check.issues.append("Uses an ## Optional section, which crawlers may skip")
    if not check.mentions_sitemap:
        check.issues.append("Doesn't point to the sitemap for pages too numerous to list")
    return check


async def check_llms_txt(client: httpx.AsyncClient, site_url: str) -> LlmsTxtCheck:
    parts = urlsplit(site_url)
    origin = f"{parts.scheme}://{parts.netloc}"
    url = f"{origin}/llms.txt"
    try:
        res = await safe_get(client, url, max_bytes=2_000_000, accept="text/plain, text/markdown")
    except (FetchError, BlockedURL):
        return LlmsTxtCheck(url=url, found=False, issues=["Couldn't fetch /llms.txt"])
    ctype = res.headers.get("content-type", "")
    if res.status >= 400 or "text/html" in ctype:
        # Many sites return their HTML 404 page with a 200; that isn't an llms.txt.
        return LlmsTxtCheck(url=url, found=False, status=res.status, issues=["No /llms.txt"])

    check = analyse(url, res.text())
    check.status = res.status
    try:
        full = await safe_get(client, f"{origin}/llms-full.txt", max_bytes=200_000)
        check.has_full_version = full.status < 400 and "text/html" not in full.headers.get("content-type", "")
    except (FetchError, BlockedURL):
        pass
    return check
