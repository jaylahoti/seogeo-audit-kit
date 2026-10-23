"""Extract everything the SEO and AI-readiness checks need from one crawled page."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urldefrag, urljoin, urlsplit

from selectolax.lexbor import LexborHTMLParser

from app.crawl.crawler import Page

BOILERPLATE_TAGS = "script, style, noscript, template, svg, nav, header, footer, aside, form"
RE_WS = re.compile(r"\s+")
RE_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class JsonLdBlock:
    raw: str
    data: object | None = None
    error: str | None = None


@dataclass
class PageFacts:
    url: str
    final_url: str
    status: int | None
    redirects: list[str]
    elapsed_ms: float
    lang: str | None = None
    title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    meta_robots: str = ""
    x_robots: str = ""
    h1s: list[str] = field(default_factory=list)
    headings: list[tuple[int, str]] = field(default_factory=list)
    main_text: str = ""
    word_count: int = 0
    images: int = 0
    images_no_alt: int = 0
    internal_links: list[str] = field(default_factory=list)
    external_links: int = 0
    hreflang: list[tuple[str, str]] = field(default_factory=list)
    jsonld: list[JsonLdBlock] = field(default_factory=list)
    meta_modified: str | None = None

    @property
    def noindex(self) -> bool:
        return "noindex" in self.meta_robots.lower() or "noindex" in self.x_robots.lower()

    @property
    def first_words(self) -> str:
        return " ".join(self.main_text.split()[:120])

    def sentences(self, limit_words: int = 250) -> list[str]:
        text = " ".join(self.main_text.split()[:limit_words])
        return [s.strip() for s in RE_SENTENCE.split(text) if s.strip()]


def _attr(node, name: str) -> str | None:
    if node is None:
        return None
    v = node.attributes.get(name)
    return v.strip() if isinstance(v, str) else None


def _norm(url: str) -> str:
    url, _ = urldefrag(url)
    return url.rstrip("/") or url


def extract(page: Page) -> PageFacts:
    facts = PageFacts(
        url=page.url,
        final_url=page.final_url or page.url,
        status=page.status,
        redirects=page.redirects,
        elapsed_ms=page.elapsed_ms,
        x_robots=page.headers.get("x-robots-tag", ""),
    )
    if not page.html:
        return facts
    tree = LexborHTMLParser(page.html)
    html_node = tree.css_first("html")
    facts.lang = _attr(html_node, "lang")

    t = tree.css_first("title")
    facts.title = RE_WS.sub(" ", t.text()).strip() if t else None
    facts.meta_description = _attr(tree.css_first('meta[name="description"]'), "content")
    facts.canonical = _attr(tree.css_first('link[rel="canonical"]'), "href")
    if facts.canonical:
        facts.canonical = urljoin(facts.final_url, facts.canonical)
    facts.meta_robots = " ".join(
        filter(None, (_attr(n, "content") for n in tree.css('meta[name="robots"], meta[name="googlebot"]')))
    )
    facts.meta_modified = _attr(tree.css_first('meta[property="article:modified_time"]'), "content")
    facts.hreflang = [
        (_attr(n, "hreflang") or "", urljoin(facts.final_url, _attr(n, "href") or ""))
        for n in tree.css('link[rel="alternate"][hreflang]')
    ]

    for node in tree.css('script[type="application/ld+json"]'):
        raw = node.text() or ""
        block = JsonLdBlock(raw=raw.strip()[:20000])
        try:
            block.data = json.loads(raw)
        except json.JSONDecodeError as e:
            block.error = f"Invalid JSON: {e.msg} at line {e.lineno}"
        facts.jsonld.append(block)

    for level in (1, 2, 3):
        for n in tree.css(f"h{level}"):
            text = RE_WS.sub(" ", n.text()).strip()
            if text:
                facts.headings.append((level, text))
    facts.h1s = [t for lvl, t in facts.headings if lvl == 1]

    imgs = tree.css("img")
    facts.images = len(imgs)
    facts.images_no_alt = sum(1 for n in imgs if not (_attr(n, "alt") or "").strip() and _attr(n, "role") != "presentation")

    host = (urlsplit(facts.final_url).hostname or "").removeprefix("www.")
    internal: set[str] = set()
    for a in tree.css("a[href]"):
        href = _attr(a, "href") or ""
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urljoin(facts.final_url, href)
        if (urlsplit(absolute).hostname or "").removeprefix("www.") == host:
            internal.add(_norm(absolute))
        else:
            facts.external_links += 1
    facts.internal_links = sorted(internal)

    # Main text: body minus navigation and other chrome.
    body = tree.body
    if body is not None:
        for n in body.css(BOILERPLATE_TAGS):
            n.decompose()
        facts.main_text = _main_text(body)
        facts.word_count = len(facts.main_text.split())
    return facts


def _main_text(body) -> str:
    """Text of the main content area.

    Pages can have several <main> or <article> elements (a search bar wrapped in its own
    <main>, say), so take the candidate with the most text. If no candidate holds at
    least a third of the body's text, the markup isn't reliable — use the whole body.
    """
    def text(node) -> str:
        return RE_WS.sub(" ", node.text(separator=" ")).strip()

    full = text(body)
    candidates = [text(n) for n in body.css("main, article, [role=main]")]
    best = max(candidates, key=len, default="")
    return best if len(best) >= len(full) / 3 else full
