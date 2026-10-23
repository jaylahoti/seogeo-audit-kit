"""Module 4 — AI-readiness rule checks, run per template on its sample pages.

Structured data, freshness and two heuristics (verdict sentence, facts up front). The
heuristics are cheap first passes; Claude confirms them on the same samples (Day 2).
"""

from __future__ import annotations

import re
from typing import Any

from app.checks.findings import Finding, TemplateContext, make
from app.checks.page_facts import PageFacts
from app.checks.seo import _days_old

# Minimal required properties for the types programmatic sites use most.
REQUIRED: dict[str, list[str | tuple[str, ...]]] = {
    "Organization": ["name", "url"],
    "LocalBusiness": ["name", "address"],
    "Place": ["name"],
    "Residence": ["name", "address"],
    "ApartmentComplex": ["name", "address"],
    "Apartment": ["name"],
    "PostalAddress": ["streetAddress", "addressLocality"],
    "Product": ["name", ("offers", "aggregateRating", "review")],
    "Offer": [("price", "priceSpecification")],
    "AggregateRating": ["ratingValue", ("reviewCount", "ratingCount")],
    "Review": ["author", ("reviewRating", "reviewBody")],
    "Article": ["headline", "datePublished", "author"],
    "BlogPosting": ["headline", "datePublished", "author"],
    "NewsArticle": ["headline", "datePublished", "author"],
    "FAQPage": ["mainEntity"],
    "Question": ["name", "acceptedAnswer"],
    "BreadcrumbList": ["itemListElement"],
    "ItemList": ["itemListElement"],
    "WebSite": ["name", "url"],
    "Event": ["name", "startDate", "location"],
    "JobPosting": ["title", "datePosted", "hiringOrganization", "description"],
    "Recipe": ["name", "recipeIngredient"],
    "SoftwareApplication": ["name", ("offers", "aggregateRating")],
}
# Types that describe the site or navigation, not the page's subject.
CHROME_TYPES = {"BreadcrumbList", "WebSite", "WebPage", "SiteNavigationElement", "SearchAction", "ImageObject"}
RE_PLACEHOLDER = re.compile(r"\{\{.*?\}\}|\$\{.*?\}|\[object Object\]|^(undefined|null|none|nan|n/a|todo|tbd)$", re.IGNORECASE)
STALE_MODIFIED_DAYS = 90
STOP = {"the", "and", "for", "of", "in", "at", "on", "a", "an", "to", "by", "with", "&", "-", "|"}


def _types(entity: dict) -> list[str]:
    t = entity.get("@type")
    return [x for x in (t if isinstance(t, list) else [t]) if isinstance(x, str)]


def entities(data: Any) -> list[dict]:
    """Every typed object in a JSON-LD payload, including nested ones (address, rating…)."""
    found: list[dict] = []

    def walk(node: Any):
        if isinstance(node, dict):
            if "@type" in node:
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return found


def missing_required(entity: dict) -> list[str]:
    missing = []
    for t in _types(entity):
        for req in REQUIRED.get(t, []):
            options = req if isinstance(req, tuple) else (req,)
            if not any(_present(entity.get(o)) for o in options):
                missing.append(f"{t}.{'|'.join(options)}")
    return missing


def _present(v: Any) -> bool:
    return v not in (None, "", [], {})


def placeholders(data: Any, path: str = "") -> list[str]:
    """Paths to empty or placeholder values: null, "", [], "{{name}}", "undefined"…"""
    bad: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k.startswith("@"):
                continue
            p = f"{path}.{k}" if path else k
            if v is None or v == "" or v == [] or v == {} or isinstance(v, str) and RE_PLACEHOLDER.search(v.strip()):
                bad.append(p)
            else:
                bad.extend(placeholders(v, p))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            bad.extend(placeholders(v, f"{path}[{i}]"))
    return bad


def _modified(p: PageFacts) -> str | None:
    stamps = [e.get("dateModified") for b in p.jsonld if b.data is not None for e in entities(b.data)]
    stamps = [s for s in stamps if isinstance(s, str)] + ([p.meta_modified] if p.meta_modified else [])
    return max(stamps) if stamps else None


def _entity_words(p: PageFacts) -> set[str]:
    name = p.h1s[0] if p.h1s else (p.title or "")
    return {w for w in re.findall(r"[a-z0-9'-]+", name.lower()) if w not in STOP and len(w) > 2}


def has_verdict(p: PageFacts) -> bool:
    """A self-contained factual sentence near the top: names the entity and states a number."""
    words = _entity_words(p)
    for s in p.sentences(250):
        n = len(s.split())
        if 8 <= n <= 45 and any(ch.isdigit() for ch in s) and words & set(re.findall(r"[a-z0-9'-]+", s.lower())):
            return True
    return False


def facts_up_front(p: PageFacts) -> bool:
    return any(ch.isdigit() for ch in " ".join(p.main_text.split()[:60]))


def run(ctx: TemplateContext) -> list[Finding]:
    ok = [p for p in ctx.samples if p.status == 200]
    out: list[Finding | None] = []

    no_ld = [p for p in ok if not p.jsonld]
    out.append(make(ctx, "jsonld_missing", "ai", "high", "No JSON-LD structured data",
                    "Without structured data, search engines and AI assistants have to guess the facts from text.", no_ld))
    broken = [p for p in ok if any(b.error for b in p.jsonld)]
    out.append(make(ctx, "jsonld_invalid", "ai", "high", "JSON-LD that doesn't parse",
                    "Invalid JSON is ignored entirely. " + next((b.error for p in broken for b in p.jsonld if b.error), ""), broken))

    parsed = {id(p): [e for b in p.jsonld if b.data is not None for e in entities(b.data)] for p in ok}
    only_chrome = [p for p in ok if parsed[id(p)] and all(set(_types(e)) <= CHROME_TYPES for e in parsed[id(p)])]
    out.append(make(ctx, "jsonld_no_entity", "ai", "medium", "Structured data doesn't describe the page's subject",
                    "Only breadcrumbs or site-level types were found. Add the main entity (the building, product, article…).",
                    only_chrome))

    missing = {id(p): sorted({m for e in parsed[id(p)] for m in missing_required(e)}) for p in ok}
    with_missing = [p for p in ok if missing[id(p)]]
    examples = sorted({m for p in with_missing for m in missing[id(p)]})[:5]
    out.append(make(ctx, "jsonld_required", "ai", "medium", "Required schema properties missing",
                    "Missing: " + ", ".join(examples) if examples else "", with_missing))

    holes = {id(p): sorted({h for b in p.jsonld if b.data is not None for h in placeholders(b.data)}) for p in ok}
    with_holes = [p for p in ok if holes[id(p)]]
    hole_examples = sorted({h for p in with_holes for h in holes[id(p)]})[:5]
    out.append(make(ctx, "jsonld_placeholders", "ai", "medium", "Empty or placeholder values in JSON-LD",
                    "Null, empty or unfilled template values tell crawlers the data is unreliable: " + ", ".join(hole_examples),
                    with_holes))

    out.append(make(ctx, "date_modified_missing", "ai", "low", "No dateModified",
                    "Answer engines weight freshness. Publish the date the page's data last changed (the newest of its sources).",
                    [p for p in ok if p.jsonld and not _modified(p)]))
    out.append(make(ctx, "date_modified_stale", "ai", "low", f"dateModified older than {STALE_MODIFIED_DAYS} days",
                    "Stale dates make the page look out of date even when its data isn't.",
                    [p for p in ok if (d := _days_old(_modified(p))) is not None and d > STALE_MODIFIED_DAYS]))

    out.append(make(ctx, "no_verdict", "ai", "medium", "No quotable verdict sentence",
                    "Answer engines lift single sentences. Add one near the top that names the entity and states its key facts.",
                    [p for p in ok if not has_verdict(p)], method="heuristic"))
    out.append(make(ctx, "facts_buried", "ai", "low", "Key facts not in the first 60 words",
                    "Put the main numbers (price, rating, size, date) at the top, not below the fold.",
                    [p for p in ok if not facts_up_front(p)], method="heuristic"))

    return [f for f in out if f]


def site_findings(robots: dict, llms: dict) -> list[dict]:
    """Site-level AI readiness: crawler policy and llms.txt."""
    out = []
    blocked = robots.get("blocked_retrieval_bots") or []
    if blocked:
        out.append({"id": "retrieval_bots_blocked", "severity": "high",
                    "title": f"robots.txt blocks {', '.join(blocked)}",
                    "detail": "Retrieval bots fetch pages to answer live questions; blocking them removes the site from those answers."})
    if not llms.get("found"):
        out.append({"id": "llms_txt_missing", "severity": "low", "title": "No /llms.txt",
                    "detail": "A short markdown guide for AI assistants: what the site is and which pages matter."})
    elif llms.get("issues"):
        out.append({"id": "llms_txt_issues", "severity": "low", "title": "llms.txt has problems",
                    "detail": "; ".join(llms["issues"])})
    return out
