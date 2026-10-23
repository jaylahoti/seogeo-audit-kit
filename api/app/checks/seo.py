"""Module 1 — technical SEO checks, run per template on its sample pages."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from urllib.parse import urldefrag

from app.checks.content import unique_share
from app.checks.findings import Finding, TemplateContext, make

TITLE_MAX, TITLE_MIN = 60, 20
DESC_MAX, DESC_MIN = 160, 70
THIN_WORDS = 150
LOW_UNIQUE = 0.2
STALE_DAYS = 180
SLOW_MS = 1500


def _norm(url: str | None) -> str:
    return urldefrag(url or "")[0].rstrip("/")


def _days_old(stamp: str | None) -> float | None:
    if not stamp:
        return None
    try:
        dt = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return (datetime.now(UTC) - dt).total_seconds() / 86400


def _dupes(values: list[str | None]) -> set[str]:
    counts = Counter(v for v in values if v)
    return {v for v, c in counts.items() if c > 1}


def run(ctx: TemplateContext) -> list[Finding]:
    s = ctx.samples
    ok = [p for p in s if p.status == 200]
    out: list[Finding | None] = []

    # Status and redirects — every sitemap URL should be a final, indexable 200.
    out.append(make(ctx, "status_error", "seo", "high", "Sitemap URLs returning errors",
                    "These URLs are in the sitemap but return 4xx/5xx. Remove them or fix the pages.",
                    [p for p in s if p.status and p.status >= 400]))
    out.append(make(ctx, "sitemap_redirect", "seo", "medium", "Sitemap URLs that redirect",
                    "List the final URL in the sitemap; redirects waste crawl budget.",
                    [p for p in s if p.redirects]))
    out.append(make(ctx, "noindex_in_sitemap", "seo", "high", "noindex pages listed in the sitemap",
                    "The sitemap asks search engines to index pages that tell them not to.",
                    [p for p in ok if p.noindex]))

    # Canonicals.
    out.append(make(ctx, "canonical_missing", "seo", "medium", "Missing canonical tag",
                    "Without a canonical, URL variants (query strings, trailing slashes) compete with each other.",
                    [p for p in ok if not p.canonical]))
    out.append(make(ctx, "canonical_elsewhere", "seo", "medium", "Canonical points to a different URL",
                    "The page is in the sitemap but names another URL as the original, so it won't be indexed itself.",
                    [p for p in ok if p.canonical and _norm(p.canonical) != _norm(p.final_url)]))

    # Titles and descriptions.
    out.append(make(ctx, "title_missing", "seo", "high", "Missing <title>", "Every page needs a unique title.",
                    [p for p in ok if not p.title]))
    dup_titles = _dupes([p.title for p in ok])
    out.append(make(ctx, "title_duplicate", "seo", "high", "Same title on different pages",
                    "The title template isn't inserting the page's own entity name.",
                    [p for p in ok if p.title in dup_titles]))
    out.append(make(ctx, "title_long", "seo", "low", f"Title longer than {TITLE_MAX} characters",
                    "Titles get cut off in search results. Shorten the template.",
                    [p for p in ok if p.title and len(p.title) > TITLE_MAX]))
    out.append(make(ctx, "title_short", "seo", "low", f"Title shorter than {TITLE_MIN} characters",
                    "Very short titles waste the most visible line in search results.",
                    [p for p in ok if p.title and len(p.title) < TITLE_MIN]))
    out.append(make(ctx, "desc_missing", "seo", "low", "Missing meta description",
                    "Google writes its own snippet, often from boilerplate.",
                    [p for p in ok if not p.meta_description]))
    dup_desc = _dupes([p.meta_description for p in ok])
    out.append(make(ctx, "desc_duplicate", "seo", "low", "Same meta description on different pages",
                    "The description template isn't page-specific.",
                    [p for p in ok if p.meta_description in dup_desc]))
    out.append(make(ctx, "desc_length", "seo", "low", f"Meta description outside {DESC_MIN}–{DESC_MAX} characters",
                    "Too short wastes the snippet; too long gets cut off.",
                    [p for p in ok if p.meta_description and not DESC_MIN <= len(p.meta_description) <= DESC_MAX]))

    # Headings and content.
    out.append(make(ctx, "h1_missing", "seo", "medium", "Missing H1", "Each page should have one H1 naming its subject.",
                    [p for p in ok if not p.h1s]))
    out.append(make(ctx, "h1_multiple", "seo", "low", "More than one H1", "Use one H1, then H2s for sections.",
                    [p for p in ok if len(p.h1s) > 1]))
    out.append(make(ctx, "thin_content", "seo", "medium", f"Thin content (under {THIN_WORDS} words)",
                    "Pages with very little text are rarely indexed. Add data or noindex until they have it.",
                    [p for p in ok if p.word_count < THIN_WORDS]))
    if len(ok) >= 3:
        uniq = unique_share(ok)
        low = [p for p, u in zip(ok, uniq, strict=True) if u < LOW_UNIQUE]
        avg = sum(uniq) / len(uniq)
        out.append(make(ctx, "near_duplicate", "seo", "high", "Mostly template boilerplate",
                        f"On average only {avg:.0%} of each page's text is unique to it. Likely cause of "
                        "'Crawled – currently not indexed'. Surface more page-specific data.",
                        low))

    # Images, language, hreflang.
    out.append(make(ctx, "img_alt", "seo", "low", "Images without alt text",
                    "Alt text helps image search and accessibility.",
                    [p for p in ok if p.images and p.images_no_alt / p.images > 0.2]))
    out.append(make(ctx, "lang_missing", "seo", "low", "No lang attribute on <html>",
                    "Declare the page language so search engines serve it to the right audience.",
                    [p for p in ok if not p.lang]))
    with_hreflang = [p for p in ok if p.hreflang]
    out.append(make(ctx, "hreflang_self", "seo", "medium", "hreflang without a self-reference",
                    "Each page's hreflang set must include the page itself.",
                    [p for p in with_hreflang if _norm(p.final_url) not in {_norm(h) for _, h in p.hreflang}]))

    # Sitemap freshness and speed.
    stale = [p for p in s if (d := _days_old(ctx.lastmods.get(p.url))) is not None and d > STALE_DAYS]
    out.append(make(ctx, "lastmod_stale", "seo", "low", f"Sitemap lastmod older than {STALE_DAYS} days",
                    "Stale lastmod values make crawlers revisit less often. Use the date the page's data last changed.",
                    stale))
    out.append(make(ctx, "lastmod_missing", "seo", "low", "No lastmod in the sitemap",
                    "lastmod tells crawlers which pages changed since their last visit.",
                    [p for p in s if not ctx.lastmods.get(p.url)]))
    out.append(make(ctx, "slow_response", "seo", "medium", f"Slow server response (over {SLOW_MS} ms)",
                    "Slow responses reduce how many pages crawlers fetch per visit.",
                    [p for p in ok if p.elapsed_ms > SLOW_MS]))

    return [f for f in out if f]


def passed_checks(findings: list[Finding]) -> list[str]:
    failed = {f.id for f in findings}
    names = {
        "status_error": "Sitemap URLs return 200", "noindex_in_sitemap": "No noindex pages in the sitemap",
        "canonical_missing": "Canonical tags present", "title_missing": "Titles present",
        "title_duplicate": "Titles are unique", "h1_missing": "H1 present", "thin_content": "No thin pages",
        "near_duplicate": "Pages have unique content", "sitemap_redirect": "Sitemap lists final URLs",
    }
    return [label for key, label in names.items() if key not in failed]

