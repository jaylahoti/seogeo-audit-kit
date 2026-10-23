from app.checks import cwv, render
from app.checks.links import pattern_regex, template_of
from app.checks.page_facts import extract
from app.crawl.crawler import Page
from app.fixes.generators import generate_llms_txt, generate_robots_txt, label, site_name


def facts(html, url="https://s.example/b/1"):
    return extract(Page(url=url, final_url=url, status=200, content_type="text/html", html=html))


def test_pattern_regex_and_template_of():
    rx = [(p, pattern_regex(p)) for p in ["/building/nyc/{id}/{slug}", "/buildings/{slug}", "/", "/{static}"]]
    assert template_of("https://s.example/building/nyc/123-45/main-st", rx) == "/building/nyc/{id}/{slug}"
    assert template_of("https://s.example/buildings/bronx/", rx) == "/buildings/{slug}"
    assert template_of("https://s.example/", rx) == "/"
    assert template_of("https://s.example/about", rx) is None


def test_render_compare_flags_js_content():
    raw = facts("<html><body><main><h1>Building</h1><p>Loading…</p></main></body></html>")
    rendered = ("<html><head><script type='application/ld+json'>{\"@type\":\"Place\",\"name\":\"B\"}</script></head>"
                "<body><main><h1>Building</h1><h2>Reviews</h2><p>" + " ".join(f"w{i}" for i in range(300)) + "</p>"
                + "".join(f"<a href='/b/{i}'>x</a>" for i in range(30)) + "</main></body></html>")
    d = render.compare(raw, rendered)
    assert d.js_text_share > 0.9 and d.js_only_headings == ["Reviews"]
    ids = {f.id for f in render.findings(d, 1000)}
    assert ids == {"js_text", "js_jsonld", "js_links"}


def test_render_no_findings_when_server_rendered():
    html = "<html><body><main><h1>B</h1><p>" + " ".join(f"w{i}" for i in range(300)) + "</p></main></body></html>"
    assert render.findings(render.compare(facts(html), html), 1000) == []


def test_cwv_parse_prefers_field_data():
    data = {
        "lighthouseResult": {"categories": {"performance": {"score": 0.42}},
                             "audits": {"largest-contentful-paint": {"numericValue": 5100}, "cumulative-layout-shift": {"numericValue": 0.02}, "total-blocking-time": {"numericValue": 700}}},
        "loadingExperience": {"metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 3100}, "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"percentile": 30}, "INTERACTION_TO_NEXT_PAINT": {"percentile": 150}}},
    }
    v = cwv.parse("https://s.example/", data)
    assert v.source == "field-url" and v.lcp_ms == 3100 and v.cls == 0.3 and v.inp_ms == 150 and v.performance == 42
    sev = {f.id: f.severity for f in cwv.findings(v, 500)}
    assert sev == {"cwv_lcp": "medium", "cwv_cls": "high"}  # INP is good; TBT ignored when INP exists


def test_cwv_lab_only():
    data = {"lighthouseResult": {"audits": {"largest-contentful-paint": {"numericValue": 1800}, "total-blocking-time": {"numericValue": 900}}}}
    v = cwv.parse("https://s.example/", data)
    assert v.source == "lab"
    assert {f.id for f in cwv.findings(v, 10)} == {"cwv_tbt"}


def test_generators():
    templates = [
        {"pattern": "/buildings/{slug}", "estimated_pages": 4000, "examples": ["https://s.example/buildings/a"], "samples": [{"title": "The Larkin | Nest"}, {"title": "Harbor View | Nest"}]},
        {"pattern": "/blog/{slug}", "estimated_pages": 60, "examples": ["https://s.example/blog/x"], "samples": [{"title": "Renting tips | Nest"}]},
        {"pattern": "/{static}", "estimated_pages": 5, "examples": ["https://s.example/about"], "samples": []},
    ]
    home = facts('<html><head><title>Nest — rentals</title><meta name="description" content="Nest lists NYC rentals with reviews."></head><body></body></html>', "https://s.example/")
    txt = generate_llms_txt("https://s.example", home, templates, ["https://s.example/sitemap.xml"])
    assert txt.startswith("# Nest\n\n> Nest lists NYC rentals with reviews.")
    assert "[Buildings](https://s.example/buildings/a): about 4,000 pages" in txt
    assert "## About" in txt and "sitemap.xml" in txt
    assert label("/building/nyc/{id}/{slug}") == "Building (nyc)"
    assert site_name(None, [], "www.s.example") == "s.example"

    robots = {"ai_crawlers": [{"agent": "GPTBot", "kind": "training", "allowed": False}, {"agent": "PerplexityBot", "kind": "retrieval", "allowed": False}]}
    r = generate_robots_txt(robots, ["https://s.example/sitemap.xml"])
    assert "User-agent: PerplexityBot" in r.split("Allow: /")[0]  # retrieval bots go in the allowed block
    assert "User-agent: GPTBot\nDisallow: /" in r  # training choice is kept
    assert r.strip().endswith("Sitemap: https://s.example/sitemap.xml")


async def test_discover_by_links_without_sitemap(monkeypatch):
    import httpx

    from app.ingest.discover import candidate_sitemaps, discover_by_links
    from app.ingest.robots import RobotsInfo
    from app.net import safe_fetch

    async def fake_resolve(host):
        return "93.184.216.34"

    monkeypatch.setattr(safe_fetch, "resolve_public", fake_resolve)
    pages = {
        "/": '<a href="/docs/a">a</a><a href="/blog/x">x</a><a href="/docs/b?q=1">skip query</a>',
        "/docs/a": '<a href="/docs/b">b</a><a href="https://other.example/">off-site</a>',
        "/blog/x": '<a href="/blog/y">y</a>',
    }

    def handler(request):
        body = pages.get(request.url.path)
        if body is None:
            return httpx.Response(200, html="<html><body>leaf</body></html>")
        return httpx.Response(200, html=f"<html><body><main>{body}</main></body></html>")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        found = await discover_by_links(client, "https://s.example", RobotsInfo(url="", found=False, status=404))
    locs = {u.loc for u in found}
    assert {"https://s.example/docs/a", "https://s.example/blog/x", "https://s.example/docs/b", "https://s.example/blog/y"} <= locs
    assert not any("other.example" in u or "?" in u for u in locs)
    assert candidate_sitemaps("https://s.example/any")[0] == "https://s.example/sitemap.xml"


async def test_count_all_reads_every_file(monkeypatch):
    import gzip

    import httpx

    from app.ingest.count import ExactCount, count_all
    from app.net import safe_fetch

    async def fake_resolve(host):
        return "93.184.216.34"

    monkeypatch.setattr(safe_fetch, "resolve_public", fake_resolve)

    def index(*locs):
        rows = "".join(f"<sitemap><loc>https://s.example{u}</loc></sitemap>" for u in locs)
        return f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</sitemapindex>'.encode()

    def urlset(paths):
        rows = "".join(f"<url><loc>https://s.example{p}</loc></url>" for p in paths)
        return f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'.encode()

    files = {
        "/sitemap.xml": index("/b-1.xml", "/b-2.xml", "/nested.xml"),
        "/nested.xml": index("/blog.xml.gz"),
        "/b-1.xml": urlset([f"/buildings/x{i}" for i in range(300)]),
        "/b-2.xml": urlset([f"/buildings/y{i}" for i in range(200)] + ["/about"]),
        "/blog.xml.gz": gzip.compress(urlset([f"/blog/p{i}" for i in range(40)])),
    }

    def handler(request):
        body = files.get(request.url.path)
        return httpx.Response(200, content=body) if body else httpx.Response(404)

    state = ExactCount()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await count_all(client, ["https://s.example/sitemap.xml"], ["/buildings/{slug}", "/blog/{slug}", "/{static}"], state)
    assert state.status == "done" and state.files_total == 3 and state.files_failed == 0
    assert state.urls == 541
    assert state.templates == {"/buildings/{slug}": 500, "/blog/{slug}": 40}
    assert state.unmatched == 1  # /about
    assert state.families["/b-#.xml"] == {"files": 2, "urls": 501}


def test_geo_score():
    from app.checks import geo

    templates = [{"pattern": "/a/{slug}", "estimated_pages": 900, "ai_score": 80},
                 {"pattern": "/b/{slug}", "estimated_pages": 100, "ai_score": 40}]
    render = [{"pattern": "/a/{slug}", "js_text_share": 0.5, "raw_jsonld": 1, "rendered_jsonld": 1, "error": None},
              {"pattern": "/b/{slug}", "js_text_share": 0.0, "raw_jsonld": 0, "rendered_jsonld": 2, "error": None}]
    robots = {"blocked_retrieval_bots": ["PerplexityBot"]}
    result = {"robots": robots, "llms_txt": {"found": False}, "render": render, "templates": templates,
              "links": {"depth": {"/a/{slug}": 2, "/b/{slug}": None}}}
    g = geo.compute(result)
    labels = [s["label"] for s in g["access"]["signals"]]
    assert any("PerplexityBot" in x for x in labels) and "No /llms.txt" in labels
    # 100 - 25 (bot) - 10 (llms) - 18 (45% JS text) - 1.5 (JSON-LD by JS on 10%) - 1.5 (10% deep) ≈ 44
    assert 42 <= g["access"]["score"] <= 46
    assert g["readiness"]["score"] == 76  # page-weighted: (80*900 + 40*100) / 1000
    assert g["partial"] is True and g["visibility"]["score"] is None
    # Visibility missing → weights renormalised over access (0.3) and readiness (0.4)
    assert g["score"] == round((g["access"]["score"] * 0.3 + 76 * 0.4) / 0.7)


def test_api_accepts_bare_domain(monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.net import safe_fetch
    from app.routers import audits

    async def fake_resolve(host):
        return "93.184.216.34"

    async def no_run(rec):
        return None

    monkeypatch.setattr(audits, "resolve_public", fake_resolve)
    monkeypatch.setattr(audits, "run_audit", no_run)
    client = TestClient(app)
    res = client.post("/audits", json={"url": "example.com"})
    assert res.status_code == 202
    assert client.get(f"/audits/{res.json()['id']}").json()["input_url"] == "https://example.com"
    assert client.post("/audits", json={"url": "ftp://example.com"}).status_code == 422
    _ = safe_fetch
