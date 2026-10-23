"""Template detection, signal 1: URL structure.

Walks path segments position by position. A segment value that many URLs share
(e.g. "buildings") stays literal; values that are mostly unique (slugs, ids) collapse
into a typed variable ({slug}, {id}, {uuid}, {date}). The result is a set of patterns
like /buildings/{slug} with the URLs behind each.

Signal 2 (HTML structure, MinHash + HDBSCAN) refines these groups once pages are
fetched — URL patterns alone can't tell /{slug} city pages from /{slug} blog posts.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from urllib.parse import unquote, urlsplit

from app.ingest.sitemap import SitemapURL

RE_ID = re.compile(r"^\d+(-\d+)*$")  # 123 or 2130763-2023160001
RE_UUID = re.compile(r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$", re.IGNORECASE)
RE_HEX = re.compile(r"^[0-9a-f]{16,}$", re.IGNORECASE)
RE_DATE = re.compile(r"^(19|20)\d{2}(-\d{2}){0,2}$")
RE_FILE = re.compile(r"^(.+)\.(html?|php|aspx?)$", re.IGNORECASE)

# A value stays literal if at least this many URLs in the group share it...
MIN_LITERAL_COUNT = 3
# ...and the position doesn't have more distinct literal-worthy values than this.
MAX_LITERALS = 25
# Templates smaller than this get folded into a "static pages" bucket.
MIN_TEMPLATE_PAGES = 3
# This many sibling patterns that differ only in one literal segment are really one
# template with a facet value there (/apartments/manhattan/{chelsea|nomad|soho}/{slug}).
MIN_SIBLINGS = 3


@dataclass
class Template:
    pattern: str
    urls: list[SitemapURL] = field(default_factory=list)
    has_query: bool = False
    # Filled in by HTML-structure reconciliation (app/ml/dom_clusters.py).
    layout: int | None = None
    variant: int = 0  # 1, 2… when one URL pattern was split into several layouts
    merged_from: list[str] = field(default_factory=list)

    @property
    def sampled(self) -> int:
        return len(self.urls)

    @property
    def estimated_pages(self) -> int:
        return round(sum(u.weight for u in self.urls))


def segments(url: str) -> list[str]:
    path = unquote(urlsplit(url).path)
    segs = [s for s in path.split("/") if s]
    if segs:
        m = RE_FILE.match(segs[-1])
        if m:
            segs[-1] = m.group(1)
    return segs


def variable_name(values: list[str]) -> str:
    if all(RE_ID.match(v) for v in values):
        return "{id}"
    if all(RE_UUID.match(v) or RE_HEX.match(v) for v in values):
        return "{uuid}"
    if all(RE_DATE.match(v) for v in values):
        return "{date}"
    return "{slug}"


def _split(group: list[tuple[list[str], SitemapURL]], pos: int, prefix: list[str], out: list[Template]):
    if not group:
        return
    depth = len(group[0][0])
    if pos == depth:
        out.append(Template(pattern="/" + "/".join(prefix), urls=[u for _, u in group]))
        return

    counts = Counter(segs[pos] for segs, _ in group)
    # The first segment is the site section (/buildings, /articles): keep every value
    # literal, however rare, unless there are so many that it's clearly a variable.
    threshold = 1 if pos == 0 else MIN_LITERAL_COUNT
    literals = {v for v, c in counts.items() if c >= threshold}

    if len(counts) == 1:
        (only,) = counts
        _split(group, pos + 1, prefix + [only], out)
        return

    if len(literals) > MAX_LITERALS:
        literals = set()

    rest = [(s, u) for s, u in group if s[pos] not in literals]
    for lit in sorted(literals):
        _split([(s, u) for s, u in group if s[pos] == lit], pos + 1, prefix + [lit], out)
    if rest:
        name = variable_name([s[pos] for s, _ in rest])
        _split(rest, pos + 1, prefix + [name], out)


def detect_url_templates(urls: list[SitemapURL]) -> list[Template]:
    by_depth: dict[int, list[tuple[list[str], SitemapURL]]] = {}
    for u in urls:
        segs = segments(u.loc)
        by_depth.setdefault(len(segs), []).append((segs, u))

    found: list[Template] = []
    for depth in sorted(by_depth):
        group = by_depth[depth]
        if depth == 0:
            found.append(Template(pattern="/", urls=[u for _, u in group]))
            continue
        _split(group, 0, [], found)

    found = absorb_into_general(merge_siblings(found))

    templates: list[Template] = []
    static = Template(pattern="/{static}")
    for t in found:
        t.has_query = any(urlsplit(u.loc).query for u in t.urls)
        if t.estimated_pages < MIN_TEMPLATE_PAGES and t.pattern != "/":
            static.urls.extend(t.urls)
        else:
            templates.append(t)
    if static.urls:
        templates.append(static)

    templates.sort(key=lambda t: t.estimated_pages, reverse=True)
    return templates


def merge_siblings(templates: list[Template]) -> list[Template]:
    """Collapse facet-value siblings into one template, repeating until nothing changes.

    Position 0 is never generalized: /buildings and /apartments are different sections.
    """
    templates = list(templates)
    while True:
        groups: dict[tuple, list[Template]] = {}
        for t in templates:
            segs = t.pattern.strip("/").split("/")
            for pos in range(1, len(segs)):
                if segs[pos].startswith("{"):
                    continue
                key = (pos, tuple(segs[:pos]), tuple(segs[pos + 1 :]), len(segs))
                groups.setdefault(key, []).append(t)
        if not groups:
            return templates
        key, members = max(groups.items(), key=lambda kv: len(kv[1]))
        if len(members) < MIN_SIBLINGS:
            return templates

        pos, before, after, _ = key
        values = [t.pattern.strip("/").split("/")[pos] for t in members]
        merged_pattern = "/" + "/".join([*before, variable_name(values), *after])
        merged = Template(pattern=merged_pattern)
        member_ids = {id(t) for t in members}
        keep: list[Template] = []
        for t in templates:
            if id(t) in member_ids or t.pattern == merged_pattern:
                merged.urls.extend(t.urls)
            else:
                keep.append(t)
        templates = [*keep, merged]


def _matches(general: list[str], specific: list[str]) -> bool:
    return (
        general != specific
        and len(general) == len(specific)
        and general[0] == specific[0]
        and all(g == s or g.startswith("{") for g, s in zip(general, specific, strict=True))
    )


def absorb_into_general(templates: list[Template]) -> list[Template]:
    """Fold a pattern into a broader one that already covers it.

    /buildings/queens/{slug}/pre-war is matched by /buildings/{slug}/{slug}/{slug}, so its
    pages belong there. When several broader patterns match, the biggest one wins.
    """
    split = {id(t): t.pattern.strip("/").split("/") for t in templates}
    # Most specific (fewest variables) first, so chains collapse into the broadest pattern.
    order = sorted(templates, key=lambda t: sum(p.startswith("{") for p in split[id(t)]))
    alive = {id(t): t for t in templates}
    for t in order:
        candidates = [
            g for g in alive.values()
            if g is not t and _matches(split[id(g)], split[id(t)])
        ]
        if candidates:
            target = max(candidates, key=lambda g: g.estimated_pages)
            target.urls.extend(t.urls)
            del alive[id(t)]
    return list(alive.values())
