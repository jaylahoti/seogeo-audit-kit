"""A synthetic 30-day access log for an audited site, so people without server logs can see the analysis.

Paths follow the site's real page types; traffic volumes, IPs and errors are invented and the
result is always labelled synthetic. IPs come from the documentation ranges (RFC 5737).
"""

from __future__ import annotations

import random
import string
import time
from datetime import UTC, datetime
from urllib.parse import urlsplit

# (user agent, share of bot traffic, chance of fetching deep pages vs popular ones)
AGENTS = [
    ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)", 0.38, 0.8),
    ("Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)", 0.16, 0.6),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)", 0.12, 0.7),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)", 0.10, 0.6),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot", 0.07, 0.3),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; ChatGPT-User/1.0; +https://openai.com/bot", 0.05, 0.1),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)", 0.05, 0.3),
    ("Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Claude-User/1.0; +Claude-User@anthropic.com)", 0.02, 0.1),
    ("meta-externalagent/1.1 (+https://developers.facebook.com/docs/sharing/webmasters/crawler)", 0.03, 0.5),
    ("Mozilla/5.0 (compatible; Bytespider; spider-feedback@bytedance.com)", 0.02, 0.9),
]
HUMAN_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def _fill(pattern: str, rng: random.Random) -> str:
    out = []
    for seg in pattern.strip("/").split("/"):
        if seg == "{id}":
            out.append(str(rng.randint(1000, 9_999_999)))
        elif seg.startswith("{"):
            out.append("-".join("".join(rng.choices(string.ascii_lowercase, k=rng.randint(4, 8))) for _ in range(rng.randint(1, 3))))
        else:
            out.append(seg)
    return "/" + "/".join(out)


def synthetic_log(templates: list[dict], seed: str, lines: int = 20_000, days: int = 30, now: float | None = None) -> str:
    rng = random.Random(seed)
    types = [t for t in templates if t.get("pattern") not in (None, "/{static}")] or [{"pattern": "/", "estimated_pages": 1}]
    weights = [max(1, t.get("estimated_pages", 1)) ** 0.6 for t in types]
    popular = {t["pattern"]: [*(urlsplit(u).path or "/" for u in t.get("examples") or []),
                              *(_fill(t["pattern"], rng) for _ in range(30))] for t in types}
    # One page type gets rate-limited for ClaudeBot, so the analysis has something to find.
    throttled = rng.choice(types)["pattern"]
    now = now if now is not None else time.time()
    out: list[tuple[float, str]] = []
    agent_weights = [a[1] for a in AGENTS] + [0.25]
    for i in range(lines):
        ts = now - rng.random() * days * 86400
        pick = rng.choices(range(len(AGENTS) + 1), agent_weights)[0]
        ua, deep = (AGENTS[pick][0], AGENTS[pick][2]) if pick < len(AGENTS) else (HUMAN_UA, 0.5)
        t = None
        if rng.random() < 0.015:
            path = rng.choice(["/robots.txt", "/robots.txt", "/llms.txt", "/sitemap.xml"])
        else:
            t = rng.choices(types, weights)[0]
            path = _fill(t["pattern"], rng) if rng.random() < deep else rng.choice(popular[t["pattern"]])
        status = rng.choice([404, 404, 301, 500]) if rng.random() < 0.01 else 200
        if "ClaudeBot" in ua and t and t["pattern"] == throttled and rng.random() < 0.3:
            status = 429
        ip = f"{rng.choice(['192.0.2', '198.51.100', '203.0.113'])}.{rng.randint(1, 254)}"
        when = datetime.fromtimestamp(ts, UTC).strftime("%d/%b/%Y:%H:%M:%S +0000")
        out.append((ts, f'{ip} - - [{when}] "GET {path} HTTP/1.1" {status} {rng.randint(800, 90000)} "-" "{ua}"'))
        if i % 400 == 0:
            out.append((ts, f'{ip} - - [{when}] "GET /_next/static/chunks/main.js HTTP/1.1" 200 1200 "-" "{ua}"'))
    out.sort()
    return "\n".join(line for _, line in out)
