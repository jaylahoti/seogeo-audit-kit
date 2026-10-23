import json

from app.checks import ai, seo
from app.checks.content import unique_share
from app.checks.findings import TemplateContext, score
from app.checks.page_facts import extract
from app.crawl.crawler import Page


def page(i, *, title=None, jsonld=None, body=None, canonical=True, status=200, desc=None, h1=None):
    url = f"https://s.example/buildings/b-{i}"
    ld = f'<script type="application/ld+json">{jsonld}</script>' if jsonld is not None else ""
    can = f'<link rel="canonical" href="{url}">' if canonical else ""
    d = f'<meta name="description" content="{desc}">' if desc else ""
    h1 = h1 or f"Building {i} on Main Street"
    body = body or (
        f"<p>{h1} has 120 units and a 4.{i} rating from {10 + i} renters.</p>"
        + "<p>" + " ".join(f"unique{i}word{k}" for k in range(200)) + "</p>"
    )
    html = f'<html lang="en"><head><title>{title or h1 + " reviews and rents | Site"}</title>{can}{d}{ld}</head><body><nav>Menu</nav><main><h1>{h1}</h1>{body}</main></body></html>'
    return extract(Page(url=url, final_url=url, status=status, content_type="text/html", html=html))


def ctx(pages, est=1000):
    return TemplateContext("/buildings/{slug}", est, pages, {p.url: "2026-10-01" for p in pages})


def ids(findings):
    return {f.id for f in findings}


def test_extract_basics():
    p = page(1, desc="A building page", jsonld='{"@type":"ApartmentComplex","name":"B1"}')
    assert p.title.startswith("Building 1") and p.canonical and p.lang == "en"
    assert p.h1s == ["Building 1 on Main Street"]
    assert "Menu" not in p.main_text  # nav stripped
    assert p.jsonld[0].data["@type"] == "ApartmentComplex"


def test_seo_duplicate_titles_and_boilerplate():
    boiler = "<p>" + " ".join(f"same{k}" for k in range(300)) + "</p>"
    pages = [page(i, title="Apartments for rent | Site", body=boiler) for i in range(4)]
    found = ids(seo.run(ctx(pages)))
    assert {"title_duplicate", "near_duplicate", "desc_missing"} <= found


def test_seo_clean_pages_pass():
    pages = [page(i, desc="x" * 100) for i in range(4)]
    found = ids(seo.run(ctx(pages)))
    assert not found & {"title_duplicate", "near_duplicate", "canonical_missing", "h1_missing", "thin_content"}
    assert min(unique_share(pages)) > 0.5


def test_finding_scales_to_template_pages():
    pages = [page(0, canonical=False), page(1), page(2), page(3)]
    f = next(f for f in seo.run(ctx(pages, est=4000)) if f.id == "canonical_missing")
    assert f.affected == 1 and f.sampled == 4 and f.pages == 1000


def test_ai_jsonld_checks():
    good = json.dumps({"@type": "ApartmentComplex", "name": "B", "dateModified": "2026-10-20",
                       "address": {"@type": "PostalAddress", "streetAddress": "1 Main", "addressLocality": "NYC"}})
    holes = json.dumps({"@type": "ApartmentComplex", "name": "{{building.name}}", "address": None})
    crumbs = json.dumps({"@type": "BreadcrumbList", "itemListElement": [1]})
    found_good = ids(ai.run(ctx([page(i, jsonld=good) for i in range(3)])))
    assert not found_good & {"jsonld_missing", "jsonld_required", "jsonld_placeholders", "date_modified_missing"}
    found_bad = ids(ai.run(ctx([page(0), page(1, jsonld="{bad json"), page(2, jsonld=holes), page(3, jsonld=crumbs)])))
    assert {"jsonld_missing", "jsonld_invalid", "jsonld_placeholders", "jsonld_required", "jsonld_no_entity"} <= found_bad


def test_verdict_heuristic():
    assert ai.has_verdict(page(1))  # "Building 1 on Main Street has 120 units and a 4.1 rating…"
    vague = page(2, body="<p>" + " ".join(f"word{k}" for k in range(300)) + "</p>")
    assert not ai.has_verdict(vague)


def test_score():
    pages = [page(i) for i in range(4)]
    fs = ai.run(ctx(pages))
    assert 0 <= score(fs, "ai") < 100  # no JSON-LD costs points
    assert score([], "seo") == 100


def test_main_text_picks_largest_main():
    body = "<main><input placeholder=search>What are you looking for?</main><main><h1>Building 9</h1>" + "<p>" + " ".join(f"w{k}" for k in range(400)) + "</p></main>"
    p = page(9, body=body)
    assert p.word_count > 300


def test_visible_placeholders():
    leaky = page(1, body="<p>Building 1 has 120 units. -% Renters recommend this building. Rent: $NaN. Hi {{name}}.</p>")
    clean = page(2, body="<p>Building 2 has 120 units. 85% of renters recommend it, up 5% this year.</p>")
    f = next(f for f in ai.run(ctx([leaky, clean])) if f.id == "visible_placeholders")
    assert f.affected == 1
    assert "-%" in f.detail and "NaN" in f.detail and "{{name}}" in f.detail
