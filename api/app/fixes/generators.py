"""Module 12 (rule-based part) — generated llms.txt and robots.txt.

Both are built from what the audit learned about the site, so they list its real
templates and sitemaps. Claude-written fixes (JSON-LD, verdict blocks, titles) come later.
"""

from __future__ import annotations

from collections import Counter
from urllib.parse import urlsplit

from app.checks.page_facts import PageFacts
from app.ingest.robots import AI_CRAWLERS

MIN_PAGES_FOR_SECTION = 10


def site_name(home: PageFacts | None, titles: list[str], host: str) -> str:
    """The site's name: the common suffix of page titles ("… | Acme"), else the home title, else the host."""
    tails = Counter()
    for t in titles:
        for sep in (" | ", " - ", " — ", " · "):
            if sep in t:
                tails[t.rsplit(sep, 1)[1].strip()] += 1
                break
    if tails:
        name, count = tails.most_common(1)[0]
        if count >= max(2, len(titles) // 3) and 1 <= len(name) <= 40:
            return name
    if home and home.title:
        return home.title.split(" | ")[0].split(" - ")[0].strip()[:60]
    return host.removeprefix("www.")


def label(pattern: str) -> str:
    """/buildings/{slug} -> "Buildings"; /building/nyc/{id}/{slug} -> "Building (nyc)"."""
    literals = [s for s in pattern.strip("/").split("/") if s and not s.startswith("{")]
    if not literals:
        return "Pages"
    head = literals[0].replace("-", " ").replace("_", " ").capitalize()
    rest = [x.replace("-", " ") for x in literals[1:3]]
    return f"{head} ({', '.join(rest)})" if rest else head


def generate_llms_txt(origin: str, home: PageFacts | None, templates: list[dict], sitemaps: list[str]) -> str:
    host = urlsplit(origin).hostname or origin
    titles = [s["title"] for t in templates for s in t.get("samples", []) if s.get("title")]
    name = site_name(home, titles, host)
    summary = (home.meta_description if home and home.meta_description else f"{name} — {host}").strip()
    main = [t for t in templates if t["pattern"] not in ("/", "/{static}") and t["estimated_pages"] >= MIN_PAGES_FOR_SECTION]
    static = next((t for t in templates if t["pattern"] == "/{static}"), None)

    lines = [f"# {name}", "", f"> {summary}", ""]
    total = sum(t["estimated_pages"] for t in templates)
    sitemap = sitemaps[0] if sitemaps else f"{origin.rstrip('/')}/sitemap.xml"
    lines += [f"The site has about {total:,} pages, too many to list here. Full set: {sitemap}", ""]

    if main:
        lines += ["## Main page types", ""]
        for t in main:
            example = t["examples"][0] if t.get("examples") else origin
            h1 = next((s["title"] for s in t.get("samples", []) if s.get("title")), None)
            like = f' — e.g. "{h1.split(" | ")[0][:70]}"' if h1 else ""
            lines.append(f"- [{label(t['pattern'])}]({example}): about {t['estimated_pages']:,} pages{like}")
        lines.append("")
    if static and static.get("examples"):
        lines += ["## About", ""]
        for url in static["examples"][:6]:
            path = urlsplit(url).path.strip("/") or "home"
            lines.append(f"- [{path.replace('-', ' ').capitalize()}]({url})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_robots_txt(robots: dict, sitemaps: list[str]) -> str:
    """AI-crawler section to merge into the existing robots.txt (keep your own Disallow rules)."""
    policy = {p["agent"]: p["allowed"] for p in robots.get("ai_crawlers", [])}
    retrieval = [a for a, kind in AI_CRAWLERS.items() if kind == "retrieval"]
    training = [a for a, kind in AI_CRAWLERS.items() if kind == "training"]
    out = [
        "# Retrieval bots fetch pages to answer live questions in ChatGPT, Perplexity and Claude.",
        "# Blocking them removes the site from those answers, so keep them allowed.",
        *[f"User-agent: {a}" for a in retrieval],
        "Allow: /",
        "",
        "# Training bots build model datasets. This keeps your current choice for each one.",
    ]
    allowed = [a for a in training if policy.get(a, True)]
    blocked = [a for a in training if not policy.get(a, True)]
    if allowed:
        out += [*[f"User-agent: {a}" for a in allowed], "Allow: /", ""]
    if blocked:
        out += [*[f"User-agent: {a}" for a in blocked], "Disallow: /", ""]
    out += ["User-agent: *", "Allow: /", ""]
    out += [f"Sitemap: {s}" for s in (sitemaps or [])]
    return "\n".join(out).rstrip() + "\n"
