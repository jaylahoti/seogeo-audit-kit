"""robots.txt: sitemap discovery, crawl permission, and the AI-crawler policy check."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.config import settings
from app.net.safe_fetch import FetchError, safe_get

# Retrieval bots fetch pages to answer a live question — blocking them costs citations.
# Training bots build model corpora — blocking them costs long-term presence, not live answers.
AI_CRAWLERS: dict[str, str] = {
    "OAI-SearchBot": "retrieval",  # ChatGPT search
    "ChatGPT-User": "retrieval",  # user-initiated ChatGPT browsing
    "PerplexityBot": "retrieval",
    "Claude-User": "retrieval",  # user-initiated Claude browsing
    "Claude-SearchBot": "retrieval",
    "GPTBot": "training",
    "ClaudeBot": "training",
    "CCBot": "training",  # Common Crawl
    "Google-Extended": "training",  # Gemini training opt-out token
    "Applebot-Extended": "training",
}


@dataclass
class CrawlerPolicy:
    agent: str
    kind: str
    allowed: bool


@dataclass
class RobotsInfo:
    url: str
    found: bool
    status: int | None
    sitemaps: list[str] = field(default_factory=list)
    ai_crawlers: list[CrawlerPolicy] = field(default_factory=list)
    _parser: RobotFileParser | None = None

    def can_fetch(self, url: str, agent: str | None = None) -> bool:
        if not self._parser:
            return True
        return self._parser.can_fetch(agent or settings.user_agent, url)

    @property
    def blocked_retrieval_bots(self) -> list[str]:
        return [p.agent for p in self.ai_crawlers if p.kind == "retrieval" and not p.allowed]


def robots_url_for(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def parse_robots(robots_url: str, text: str, status: int) -> RobotsInfo:
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(text.splitlines())
    sitemaps = parser.site_maps() or []
    origin = robots_url.rsplit("/robots.txt", 1)[0]
    home = origin + "/"
    policies = [
        CrawlerPolicy(agent=a, kind=k, allowed=parser.can_fetch(a, home))
        for a, k in AI_CRAWLERS.items()
    ]
    return RobotsInfo(
        url=robots_url,
        found=True,
        status=status,
        sitemaps=list(dict.fromkeys(sitemaps)),
        ai_crawlers=policies,
        _parser=parser,
    )


async def fetch_robots(client: httpx.AsyncClient, site_url: str) -> RobotsInfo:
    robots_url = robots_url_for(site_url)
    try:
        res = await safe_get(client, robots_url, max_bytes=500_000, accept="text/plain")
    except FetchError:
        return RobotsInfo(url=robots_url, found=False, status=None)
    if res.status >= 400:
        # Per RFC 9309, a missing robots.txt means everything is allowed.
        return RobotsInfo(
            url=robots_url,
            found=False,
            status=res.status,
            ai_crawlers=[CrawlerPolicy(a, k, True) for a, k in AI_CRAWLERS.items()],
        )
    return parse_robots(robots_url, res.text(), res.status)
