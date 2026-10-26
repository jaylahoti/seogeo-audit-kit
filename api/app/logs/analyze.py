"""Crawler analytics: which bots fetch which page types, how often, and what they get back.

Lines are aggregated as they're read, so memory stays flat however long the log is.
Bots that support verification (Google, Bing, Apple) are checked with forward-confirmed
reverse DNS; requests that claim to be them but fail are counted as spoofed and left out.
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime

from app.ingest.count import classifier
from app.logs.bots import AI_KINDS, BOTS, identify, verify_ips
from app.logs.parse import Hit, parse

ASSET = re.compile(r"\.(js|mjs|css|map|png|jpe?g|gif|webp|avif|svg|ico|woff2?|ttf|mp4|webm|json|txt|xml)$", re.IGNORECASE)
SPECIAL = {"/robots.txt": "robots.txt", "/llms.txt": "llms.txt", "/llms-full.txt": "llms-full.txt"}
MAX_DISTINCT = 200_000  # distinct paths remembered per page type
OTHER = "other pages"


def _special(path: str) -> str | None:
    if path in SPECIAL:
        return SPECIAL[path]
    if path.startswith("/sitemap") and path.endswith((".xml", ".xml.gz")):
        return "sitemaps"
    return None


async def analyze(text: str, templates: list[dict], verify: bool = True, synthetic: bool = False) -> dict:
    patterns = [t["pattern"] for t in templates if t.get("pattern") not in (None, "/{static}")]
    classify = classifier(patterns)
    est = {t["pattern"]: t.get("estimated_pages", 0) for t in templates}

    lines = unread = assets = humans = 0
    first = last = None
    hits: dict[str, Counter] = defaultdict(Counter)  # bot -> page type -> n
    status: dict[str, Counter] = defaultdict(Counter)  # bot -> status class
    last_seen: dict[str, float] = {}
    special: dict[str, Counter] = defaultdict(Counter)  # bot -> robots.txt/llms.txt/sitemaps -> n
    errors: Counter = Counter()  # (bot, page type, status) -> n
    error_paths: dict[tuple, str] = {}
    distinct_ai: dict[str, set] = defaultdict(set)  # page type -> paths fetched by AI bots
    daily: dict[str, Counter] = defaultdict(Counter)  # yyyy-mm-dd -> kind -> n
    ips: dict[str, set] = defaultdict(set)  # bot -> IPs, for verification
    kept: list[tuple[str, Hit, str | None]] = []  # verifiable bots only: decided after DNS

    def record(name: str, kind: str, h: Hit, ptype: str | None):
        sp = _special(h.path)
        if sp:
            special[name][sp] += 1
            return
        pt = ptype or OTHER
        hits[name][pt] += 1
        status[name][f"{h.status // 100}xx"] += 1
        if h.ts:
            last_seen[name] = max(last_seen.get(name, 0), h.ts)
            day = datetime.fromtimestamp(h.ts, UTC).strftime("%Y-%m-%d")
            daily[day]["ai" if kind in AI_KINDS else "search"] += 1
        if h.status >= 400:
            errors[(name, pt, h.status)] += 1
            error_paths.setdefault((name, pt, h.status), h.path)
        if kind in AI_KINDS and h.status < 400 and len(distinct_ai[pt]) < MAX_DISTINCT:
            distinct_ai[pt].add(h.path)

    for h in parse(text):
        lines += 1
        if h is None:
            unread += 1
            continue
        if h.ts:
            first = h.ts if first is None else min(first, h.ts)
            last = h.ts if last is None else max(last, h.ts)
        bot = identify(h.ua)
        if bot is None:
            humans += 1
            continue
        if ASSET.search(h.path) and not _special(h.path):
            assets += 1
            continue
        ptype = classify("https://x" + h.path) if not _special(h.path) else None
        if bot.rdns and verify and h.ip:
            ips[bot.name].add(h.ip)
            kept.append((bot.name, h, ptype))
            continue
        record(bot.name, bot.kind, h, ptype)

    # Verify the bots that support it, then count the ones that checked out (or couldn't be checked).
    checked = await verify_ips({(n, ip) for n, s in ips.items() for ip in s}) if kept else {}
    spoofed: Counter = Counter()
    by_name = {b.name: b for b in BOTS}
    for name, h, ptype in kept:
        if checked.get((name, h.ip)) is False:
            spoofed[name] += 1
            continue
        record(name, by_name[name].kind, h, ptype)

    bots_out = []
    for b in BOTS:
        if b.name not in hits and b.name not in special and not spoofed.get(b.name):
            continue
        total = sum(hits[b.name].values())
        st = status[b.name]
        bad = st.get("4xx", 0) + st.get("5xx", 0)
        n_ips = len(ips.get(b.name, ()))
        n_ok = sum(1 for (n, _), ok in checked.items() if n == b.name and ok)
        bots_out.append({
            "name": b.name, "operator": b.operator, "kind": b.kind, "hits": total,
            "by_page_type": dict(hits[b.name].most_common()),
            "status": dict(st), "error_rate": round(bad / total, 4) if total else 0,
            "last_seen": last_seen.get(b.name), "special": dict(special[b.name]),
            "verification": (
                "unverified" if not b.rdns else
                "not checked" if not verify or synthetic else
                f"{n_ok} of {n_ips} IPs verified" if n_ips else "no IPs in log"
            ),
            "spoofed": spoofed.get(b.name, 0),
        })
    bots_out.sort(key=lambda x: -x["hits"])

    page_types = []
    for p in [*patterns, OTHER]:
        ai_hits = sum(hits[b.name].get(p, 0) for b in BOTS if b.kind in AI_KINDS)
        search_hits = sum(hits[b.name].get(p, 0) for b in BOTS if b.kind == "search")
        if not ai_hits and not search_hits and p == OTHER:
            continue
        seen = len(distinct_ai.get(p, ()))
        pages = est.get(p, 0)
        page_types.append({
            "pattern": p, "estimated_pages": pages, "ai_hits": ai_hits, "search_hits": search_hits,
            "ai_distinct_pages": seen, "ai_coverage": round(min(1.0, seen / pages), 4) if pages else None,
        })

    top_errors = [
        {"bot": n, "page_type": pt, "status": s, "count": c, "example": error_paths[(n, pt, s)]}
        for (n, pt, s), c in errors.most_common(10)
    ]
    ai_total = sum(x["hits"] for x in bots_out if x["kind"] in AI_KINDS)
    ai_errors = sum(x["status"].get("4xx", 0) + x["status"].get("5xx", 0) for x in bots_out if x["kind"] in AI_KINDS)
    kind_of = {b.name: b.kind for b in BOTS}
    llms_by = sorted((n for n, s in special.items() if s.get("llms.txt")), key=lambda n: (kind_of[n] == "search", n))

    return {
        "analyzed_at": time.time(),
        "synthetic": synthetic,
        "lines": lines, "unread_lines": unread, "asset_requests": assets, "other_requests": humans,
        "from": first, "to": last,
        "ai_hits": ai_total, "ai_error_rate": round(ai_errors / ai_total, 4) if ai_total else 0,
        "llms_txt_fetched_by": llms_by,
        "bots": bots_out, "page_types": page_types, "top_errors": top_errors,
        "daily": [{"day": d, **c} for d, c in sorted(daily.items())][-90:],
        "spoofed": sum(spoofed.values()),
    }
