"""Known crawlers, identified by user agent, and how to verify the ones that support it.

Kinds:
  training   collects pages for model training (blocking it costs long-term presence)
  ai_search  builds the index an AI search product answers from
  ai_user    fetches a page live because a user asked the assistant about it
  search     classic search engine crawler (Google, Bing feed AI answers too)
"""

from __future__ import annotations

import asyncio
import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class Bot:
    name: str
    token: str  # substring of the user agent, matched case-insensitively
    operator: str
    kind: str
    rdns: tuple[str, ...] = ()  # hostname suffixes for forward-confirmed reverse DNS, when the operator supports it


# Order matters only where one token contains another (none do today).
BOTS: list[Bot] = [
    Bot("GPTBot", "gptbot", "OpenAI", "training"),
    Bot("OAI-SearchBot", "oai-searchbot", "OpenAI", "ai_search"),
    Bot("ChatGPT-User", "chatgpt-user", "OpenAI", "ai_user"),
    Bot("ClaudeBot", "claudebot", "Anthropic", "training"),
    Bot("Claude-SearchBot", "claude-searchbot", "Anthropic", "ai_search"),
    Bot("Claude-User", "claude-user", "Anthropic", "ai_user"),
    Bot("PerplexityBot", "perplexitybot", "Perplexity", "ai_search"),
    Bot("Perplexity-User", "perplexity-user", "Perplexity", "ai_user"),
    Bot("MistralAI-User", "mistralai-user", "Mistral", "ai_user"),
    Bot("DuckAssistBot", "duckassistbot", "DuckDuckGo", "ai_user"),
    Bot("Meta-ExternalAgent", "meta-externalagent", "Meta", "training"),
    Bot("Amazonbot", "amazonbot", "Amazon", "training"),
    Bot("Bytespider", "bytespider", "ByteDance", "training"),
    Bot("CCBot", "ccbot", "Common Crawl", "training"),
    Bot("Applebot", "applebot", "Apple", "search", ("applebot.apple.com",)),
    Bot("Googlebot", "googlebot", "Google", "search", ("googlebot.com", "google.com")),
    Bot("Bingbot", "bingbot", "Microsoft", "search", ("search.msn.com",)),
]

AI_KINDS = {"training", "ai_search", "ai_user"}


def identify(user_agent: str) -> Bot | None:
    ua = user_agent.lower()
    for b in BOTS:
        if b.token in ua:
            return b
    return None


def _fcrdns(ip: str, suffixes: tuple[str, ...]) -> bool:
    """Reverse-resolve the IP, check the domain, then resolve that name forward and require the same IP."""
    try:
        host = socket.gethostbyaddr(ip)[0].rstrip(".").lower()
    except OSError:
        return False
    if not any(host == s or host.endswith("." + s) for s in suffixes):
        return False
    try:
        return ip in {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except OSError:
        return False


async def verify_ips(pairs: set[tuple[str, str]], limit: int = 300, timeout: float = 3.0) -> dict[tuple[str, str], bool]:
    """pairs: (bot name, ip) for bots that support rDNS. Returns which ones checked out.
    Capped so a huge log can't turn into thousands of DNS lookups; unchecked pairs are left out."""
    by_name = {b.name: b for b in BOTS}
    sem = asyncio.Semaphore(20)
    out: dict[tuple[str, str], bool] = {}

    async def one(pair: tuple[str, str]):
        name, ip = pair
        async with sem:
            try:
                ok = await asyncio.wait_for(asyncio.to_thread(_fcrdns, ip, by_name[name].rdns), timeout)
            except TimeoutError:
                return
            out[pair] = ok

    await asyncio.gather(*(one(p) for p in sorted(pairs)[:limit]))
    return out
