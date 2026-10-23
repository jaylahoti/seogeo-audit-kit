import gzip

import httpx
import pytest

from app.ingest.robots import parse_robots
from app.ingest.sitemap import SitemapURL, ingest_sitemaps, parse_sitemap_xml
from app.ml.url_patterns import detect_url_templates
from app.net import safe_fetch
from app.net.safe_fetch import BlockedURL, check_url, is_blocked_ip

# --- SSRF guard -------------------------------------------------------------

@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.1", "169.254.169.254",  # cloud metadata
    "0.0.0.0", "::1", "fd00::1", "fe80::1", "::ffff:127.0.0.1", "100.64.0.1",
])
def test_blocks_internal_ips(ip):
    assert is_blocked_ip(ip)


@pytest.mark.parametrize("ip", ["93.184.216.34", "1.1.1.1", "2606:4700:4700::1111"])
def test_allows_public_ips(ip):
    assert not is_blocked_ip(ip)


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com/x", "http://user:pw@example.com/",
    "http://example.com:6379/", "gopher://example.com",
])
def test_rejects_bad_urls(url):
    with pytest.raises(BlockedURL):
        check_url(url)


async def test_redirect_to_internal_is_blocked(monkeypatch):
    async def fake_resolve(host):
        if host == "evil.example":
            return "93.184.216.34"
        return await real_resolve(host)

    real_resolve = safe_fetch.resolve_public
    monkeypatch.setattr(safe_fetch, "resolve_public", fake_resolve)

    def handler(request: httpx.Request):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(BlockedURL):
            await safe_fetch.safe_get(client, "http://evil.example/")


# --- robots.txt -------------------------------------------------------------

def test_robots_ai_policy():
    text = """
User-agent: GPTBot
Disallow: /

User-agent: PerplexityBot
Disallow: /

User-agent: *
Allow: /

Sitemap: https://site.example/sitemap.xml
"""
    info = parse_robots("https://site.example/robots.txt", text, 200)
    assert info.sitemaps == ["https://site.example/sitemap.xml"]
    policy = {p.agent: p.allowed for p in info.ai_crawlers}
    assert policy["GPTBot"] is False
    assert policy["OAI-SearchBot"] is True
    assert info.blocked_retrieval_bots == ["PerplexityBot"]


# --- sitemaps ---------------------------------------------------------------

INDEX = b"""<?xml version="1.0"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://site.example/a.xml</loc></sitemap>
  <sitemap><loc>https://site.example/b.xml.gz</loc></sitemap>
</sitemapindex>"""


def urlset(locs):
    rows = "".join(f"<url><loc>{u}</loc><lastmod>2026-10-01</lastmod></url>" for u in locs)
    return f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'.encode()


def test_parse_urlset():
    kind, entries = parse_sitemap_xml(urlset(["https://site.example/x"]))
    assert kind == "urlset" and entries[0].loc == "https://site.example/x"
    assert entries[0].lastmod == "2026-10-01"


def test_rejects_xml_bomb():
    bomb = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><urlset>&b;</urlset>'
    with pytest.raises(ValueError):  # defusedxml's errors subclass ValueError
        parse_sitemap_xml(bomb)


async def test_ingest_samples_every_sitemap(monkeypatch):
    async def fake_resolve(host):
        return "93.184.216.34"

    monkeypatch.setattr(safe_fetch, "resolve_public", fake_resolve)
    a = [f"https://site.example/buildings/b-{i}" for i in range(1000)]
    b = [f"https://site.example/landlords/l-{i}" for i in range(100)]

    def handler(request: httpx.Request):
        path = request.url.path
        if path == "/sitemap.xml":
            return httpx.Response(200, content=INDEX)
        if path == "/a.xml":
            return httpx.Response(200, content=urlset(a))
        if path == "/b.xml.gz":
            return httpx.Response(200, content=gzip.compress(urlset(b)))
        return httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        res = await ingest_sitemaps(client, ["https://site.example/sitemap.xml"], max_urls=200)

    patterns = {t.pattern: t.estimated_pages for t in detect_url_templates(res.urls)}
    # Both sitemaps sampled, and counts scale back up to the real totals.
    assert patterns["/buildings/{slug}"] == 1000
    assert patterns["/landlords/{slug}"] == 100
    assert res.truncated
    fams = {f.family: f for f in res.families}
    assert fams["/a.xml"].urls_listed == 1000 and fams["/a.xml"].estimated == 1000
    assert fams["/b.xml.gz"].files_read == 1 and res.leaves_total == 2 and res.leaves_read == 2


# --- template detection -----------------------------------------------------

def U(path):
    return SitemapURL(loc=f"https://site.example{path}")


def test_detects_templates():
    urls = (
        [U(f"/building/nyc/{1000 + i}/street-{i}") for i in range(50)]
        + [U(f"/neighborhoods/hood-{i}") for i in range(20)]
        + [U(f"/articles/compare/a-vs-b-{i}") for i in range(10)]
        + [U(f"/articles/guides/guide-{i}") for i in range(10)]
        + [U("/about"), U("/contact"), U("/")]
    )
    patterns = {t.pattern: t.sampled for t in detect_url_templates(urls)}
    assert patterns["/building/nyc/{id}/{slug}"] == 50
    assert patterns["/neighborhoods/{slug}"] == 20
    assert patterns["/articles/compare/{slug}"] == 10
    assert patterns["/articles/guides/{slug}"] == 10
    assert patterns["/{static}"] == 2
    assert patterns["/"] == 1


def test_merges_facet_siblings():
    hoods = ["chelsea", "nomad", "soho", "tribeca"]
    urls = [U(f"/apartments/manhattan/{h}/listing-{i}") for h in hoods for i in range(5)]
    urls += [U(f"/apartments/brooklyn/{h}/listing-{i}") for h in ["dumbo", "bushwick", "red-hook"] for i in range(5)]
    urls += [U(f"/apartments/queens/{h}/listing-{i}") for h in ["astoria", "flushing", "jamaica"] for i in range(5)]
    urls += [U(f"/building/nyc/{2130763 + i}-2023160001/street-{i}") for i in range(10)]
    patterns = {t.pattern: t.sampled for t in detect_url_templates(urls)}
    assert patterns["/apartments/{slug}/{slug}/{slug}"] == 50
    assert patterns["/building/nyc/{id}/{slug}"] == 10


def test_pick_leaves_covers_every_family():
    from app.ingest.sitemap import pick_leaves

    leaves = [f"https://s.example/sitemap_apartments__{i:03}.xml" for i in range(1, 181)]
    leaves += [f"https://s.example/sitemap_verified__{i:03}.xml" for i in range(1, 4)]
    leaves += ["https://s.example/sitemap_articles.xml"]
    picked = pick_leaves(leaves, 10)
    assert len(picked) == 10
    assert "https://s.example/sitemap_articles.xml" in picked
    assert sum("verified" in p for p in picked) == 3


def test_llms_txt_analysis():
    from app.ingest.llms_txt import analyse

    good = """# Example Rentals

> Example Rentals lists apartments and verified tenant reviews.

Entity pages are too many to list; see https://site.example/sitemap.xml

## Entity pages

- [Buildings](https://site.example/buildings): One page per building.

## Guides

- [Guides](https://site.example/guides): Renting guides.
"""
    c = analyse("https://site.example/llms.txt", good)
    assert c.title == "Example Rentals" and c.has_summary
    assert c.sections == ["Entity pages", "Guides"]
    assert c.links == 2 and c.issues == []

    bad = "Some text\n- [Home](http://localhost:3000/)\n## Optional\n"
    issues = analyse("https://site.example/llms.txt", bad).issues
    assert any("H1" in i for i in issues)
    assert any("localhost" in i for i in issues)
    assert any("Optional" in i for i in issues)
