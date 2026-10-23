"""Content similarity within a template, and representative sampling."""

from __future__ import annotations

import re

from app.checks.page_facts import PageFacts

RE_TOKEN = re.compile(r"[a-z0-9]+")
SHINGLE = 5  # words per shingle


def shingles(text: str) -> set[int]:
    words = RE_TOKEN.findall(text.lower())
    return {hash(" ".join(words[i : i + SHINGLE])) for i in range(max(0, len(words) - SHINGLE + 1))}


def unique_share(pages: list[PageFacts]) -> list[float]:
    """For each page, the share of its 5-word shingles that no other sampled page has.

    Low values mean the page is mostly template boilerplate, with little unique data —
    the usual cause of "Crawled – currently not indexed" on programmatic sites.
    """
    sets = [shingles(p.main_text) for p in pages]
    out = []
    for i, s in enumerate(sets):
        if not s:
            out.append(0.0)
            continue
        others = set().union(*(sets[j] for j in range(len(sets)) if j != i)) if len(sets) > 1 else set()
        out.append(len(s - others) / len(s))
    return out


def pick_samples(pages: list[PageFacts], lastmods: dict[str, str | None], n: int = 5) -> list[PageFacts]:
    """Representative pages: longest, shortest, most recently modified, most unusual, then spread."""
    pool = [p for p in pages if p.status == 200]
    if len(pool) <= n:
        return pool
    chosen: list[PageFacts] = []

    def add(p: PageFacts | None):
        if p is not None and p not in chosen and len(chosen) < n:
            chosen.append(p)

    add(max(pool, key=lambda p: p.word_count))
    add(min(pool, key=lambda p: p.word_count))
    dated = [p for p in pool if lastmods.get(p.url)]
    if dated:
        add(max(dated, key=lambda p: lastmods[p.url] or ""))
    uniq = unique_share(pool)
    add(pool[max(range(len(pool)), key=lambda i: uniq[i])])
    for p in pool:  # fill in sitemap order, which is already spread through the site
        add(p)
    return chosen
