from app.ingest.sitemap import SitemapURL
from app.ml.dom_clusters import Sampled, cluster_layouts, fingerprint, reconcile
from app.ml.url_patterns import Template


def listing_page(i):
    return f"""<html><body><header class="Header_root__a1B2c"><nav><a>Home</a></nav></header>
    <main><section class="hero"><h1>Listing {i}</h1><p>Rent</p></section>
    <section class="facts"><ul><li>Beds</li><li>Baths</li></ul></section>
    <section class="reviews"><article><h3>Review</h3><p>Nice</p></article></section></main>
    <footer><p>©</p></footer></body></html>"""


def hub_page(i):
    return f"""<html><body><header class="Header_root__zz9Yx"><nav><a>Home</a></nav></header>
    <main><div class="grid"><div class="card"><img/><h2>Area {i}</h2></div>
    <div class="card"><img/><h2>Other</h2></div></div><aside class="filters"><form><input/>
    <select><option>1</option></select></form></aside></main><footer><p>©</p></footer></body></html>"""


def test_fingerprint_ignores_entity_names_and_classes():
    a, b = fingerprint(listing_page(1)), fingerprint(listing_page(2))
    assert a.paths == b.paths  # class hashes differ only in the real world; names ignored
    assert a.headings == b.headings  # "Listing 1" vs "Listing 2" -> same skeleton


def test_heading_skeleton_strips_entity():
    page = "<body><h1>25 Lincoln Avenue</h1><h2>Reviews of 25 Lincoln Avenue</h2><h2>Rents in 2026</h2></body>"
    assert fingerprint(page).headings == {"<h1>", "reviews of", "rents in #"}


def test_clusters_two_layouts():
    prints = [fingerprint(listing_page(i)) for i in range(6)] + [fingerprint(hub_page(i)) for i in range(6)]
    res = cluster_layouts(prints)
    first, second = set(res.labels[:6]), set(res.labels[6:])
    assert len(first) == 1 and len(second) == 1 and first != second
    assert res.coords and len(res.coords) == 12


def U(path, w=1.0):
    return SitemapURL(loc=f"https://s.example{path}", weight=w)


def test_split_and_merge():
    mixed = Template("/buildings/{slug}", urls=[U(f"/buildings/x{i}", 10) for i in range(8)])
    a = Template("/apartments/manhattan/{slug}/{slug}", urls=[U(f"/apartments/manhattan/a/l{i}") for i in range(4)])
    b = Template("/apartments/queens/hunters-point/{slug}", urls=[U(f"/apartments/queens/hunters-point/l{i}") for i in range(4)])
    samples = (
        [Sampled(0, f"https://s.example/buildings/x{i}", 0 if i < 4 else 1) for i in range(8)]
        + [Sampled(1, f"https://s.example/apartments/manhattan/a/l{i}", 2) for i in range(4)]
        + [Sampled(2, f"https://s.example/apartments/queens/hunters-point/l{i}", 2) for i in range(4)]
    )
    out = {(t.pattern, t.variant): t for t in reconcile([mixed, a, b], samples)}
    assert out[("/buildings/{slug}", 1)].estimated_pages + out[("/buildings/{slug}", 2)].estimated_pages == 80
    merged = out[("/apartments/{slug}/{slug}/{slug}", 0)]
    assert merged.sampled == 8 and len(merged.merged_from) == 2
