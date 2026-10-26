"""Synthetic programmatic sites with known answers, for evals.

Each site has page types built from distinct layouts, with the traps real sites have:
  * one URL pattern serving two layouts (should be split),
  * two URL patterns sharing one layout (should be merged),
  * pages within a type that vary (optional sections, different list lengths),
  * bugs planted per page type, on every page or on a share of them,
  * a quotable summary sentence on some types, a decoy sentence (entity + number, but not
    a summary) on others, and key facts up front or buried.

Everything is generated, so the ground truth is exact and nothing is copied from real sites.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

WORDS = ["quiet", "bright", "spacious", "modern", "classic", "renovated", "sunny", "corner", "garden", "rooftop", "lobby", "laundry", "doorman", "elevator", "parking", "storage", "gym", "pool", "terrace", "balcony", "courtyard", "hardwood", "granite", "marble", "stainless", "window", "closet", "kitchen", "bedroom", "bathroom", "studio", "loft", "view", "river", "park", "station", "market", "cafe", "school", "library", "museum", "transit", "bus", "subway", "commute", "walk", "bike", "neighbor", "friendly", "helpful", "responsive", "maintenance", "repair", "heating", "cooling", "water", "pressure", "noise", "light", "space", "value", "price", "deal", "fair", "clean", "safe", "secure", "pet", "dog", "cat", "policy", "lease", "term", "deposit", "fee", "utility", "included"]
CHECKED = [  # finding ids whose ground truth the generator controls
    "canonical_missing", "title_missing", "title_duplicate", "desc_missing", "h1_missing", "h1_multiple",
    "thin_content", "img_alt", "lang_missing", "jsonld_missing", "jsonld_required", "jsonld_placeholders",
    "date_modified_missing", "visible_placeholders",
]


@dataclass
class PageType:
    name: str  # ground-truth label
    url: str  # URL pattern with {slug} / {id} / {date}
    layout: str
    count: int
    bugs: dict[str, float] = field(default_factory=dict)  # finding id -> share of pages that have it
    verdict: str = "yes"  # "yes" (quotable summary) | "decoy" (entity + number, not a summary) | "no"
    facts_first: bool = True
    schema: str = "Place"


@dataclass
class SynthPage:
    url: str
    html: str
    label: str
    bugs: set[str]
    verdict: bool
    facts_first: bool


@dataclass
class Site:
    name: str
    host: str
    types: list[PageType]
    pages: list[SynthPage] = field(default_factory=list)


def _prose(rng: random.Random, n: int) -> str:
    out, sent = [], []
    for _ in range(n):
        sent.append(rng.choice(WORDS))
        if len(sent) >= rng.randint(9, 16):
            out.append(" ".join(sent).capitalize() + ".")
            sent = []
    if sent:
        out.append(" ".join(sent).capitalize() + ".")
    return " ".join(out)


def _name(rng: random.Random) -> str:
    # Some names carry a number ("25 Lincoln Avenue"), which is exactly what fools number-based heuristics.
    base = f"{rng.choice(['North', 'Elm', 'Harbor', 'Maple', 'Cedar', 'Union', 'Grand', 'Park', 'Lake', 'Hill', 'Stone', 'Bay'])} " \
           f"{rng.choice(['Tower', 'House', 'Court', 'Place', 'Works', 'Studio', 'Market', 'Point', 'Gardens', 'Yard', 'Hall', 'Row'])}"
    return f"{rng.randint(2, 999)} {base}" if rng.random() < 0.3 else base


def _fill(pattern: str, rng: random.Random, name: str) -> str:
    slug = name.lower().replace(" ", "-")
    out = pattern.replace("{slug}", f"{slug}-{rng.randint(10, 99999)}", 1).replace("{slug}", rng.choice(["brooklyn", "queens", "austin", "denver", "boston"]))
    out = out.replace("{id}", str(rng.randint(10_000, 9_999_999)))
    return out.replace("{date}", f"20{rng.randint(20, 26)}-{rng.randint(1, 12):02d}")


# --- layouts -------------------------------------------------------------------------------
# Each returns the <main> markup. `h1` is "" when the page has its h1 replaced.

def _img(alt_ok: bool, rng: random.Random) -> str:
    return f'<img src="/i/{rng.randint(1, 9999)}.jpg"{" alt=\"photo\"" if alt_ok else ""}>'


def layout_profile(c: dict, rng: random.Random) -> str:
    facts = "".join(f"<dt>{rng.choice(WORDS)}</dt><dd>{rng.randint(1, 900)}</dd>" for _ in range(rng.randint(4, 8)))
    reviews = "".join(f"<article><h3>{rng.choice(WORDS).title()} review</h3><p>{_prose(rng, 40)}</p></article>" for _ in range(rng.randint(1, 4)))
    extra = f'<aside class="map"><div>{_img(c["alt"], rng)}</div></aside>' if rng.random() < 0.6 else ""
    return (f'<main><section class="hero">{c["h1"]}<p>{c["lead"]}</p></section>'
            f'<section class="facts"><h2>Building facts</h2><dl>{facts}</dl></section>'
            f'<section class="reviews"><h2>Reviews</h2>{reviews}</section>{extra}'
            f'<section class="about"><h2>About</h2><p>{c["body"]}</p></section></main>')


def layout_claimed(c: dict, rng: random.Random) -> str:
    badges = "".join(f"<li>{rng.choice(WORDS)}</li>" for _ in range(rng.randint(3, 6)))
    gallery = "".join(f"<figure>{_img(c['alt'], rng)}<figcaption>{rng.choice(WORDS)}</figcaption></figure>" for _ in range(rng.randint(3, 6)))
    rows = "".join(f"<tr><td>{rng.choice(WORDS)}</td><td>${rng.randint(900, 5000)}</td></tr>" for _ in range(rng.randint(3, 6)))
    return (f'<main><div class="banner">{_img(c["alt"], rng)}</div><div class="cols"><div class="left">{c["h1"]}'
            f'<p>{c["lead"]}</p><ul class="badges">{badges}</ul><table>{rows}</table></div>'
            f'<div class="right"><form><input name="a"><input name="b"><textarea></textarea><button>Contact</button></form></div></div>'
            f'<section class="gallery">{gallery}</section><div class="text"><p>{c["body"]}</p></div></main>')


def layout_hub(c: dict, rng: random.Random) -> str:
    cards = "".join(f'<li class="card"><a href="/x/{rng.randint(1, 9999)}">{_img(c["alt"], rng)}<h2>{rng.choice(WORDS).title()} {rng.randint(1, 99)}</h2></a><p>{_prose(rng, 18)}</p></li>' for _ in range(rng.randint(6, 12)))
    return (f'<main>{c["h1"]}<p>{c["lead"]}</p><div class="filters"><form><select><option>Any</option></select>'
            f'<select><option>Price</option></select></form></div><ul class="grid">{cards}</ul>'
            f'<nav class="pages"><a>1</a><a>2</a><a>3</a></nav><p>{c["body"]}</p></main>')


def layout_article(c: dict, rng: random.Random) -> str:
    paras = "".join(f"<p>{_prose(rng, 50)}</p>" for _ in range(rng.randint(3, 6)))
    quote = f"<blockquote>{_prose(rng, 20)}</blockquote>" if rng.random() < 0.5 else ""
    return (f'<main><article><header>{c["h1"]}<time>2026-10-01</time><span class="by">Staff</span></header>'
            f'<p>{c["lead"]}</p>{paras}<h2>What to know</h2>{quote}<p>{c["body"]}</p>'
            f'<figure>{_img(c["alt"], rng)}</figure></article></main>')


def layout_person(c: dict, rng: random.Random) -> str:
    rows = "".join(f"<tr><td>{rng.choice(WORDS)}</td><td>{rng.randint(1, 300)}</td><td>{rng.choice(WORDS)}</td><td>{rng.randint(1, 5)}</td></tr>" for _ in range(rng.randint(3, 8)))
    faq = "".join(f"<details><summary>{rng.choice(WORDS).title()}?</summary><p>{_prose(rng, 25)}</p></details>" for _ in range(rng.randint(2, 5)))
    return (f'<main><div class="profile">{_img(c["alt"], rng)}{c["h1"]}<p>{c["lead"]}</p></div>'
            f'<h2>Properties</h2><table class="props">{rows}</table><section class="faq"><h2>FAQ</h2>{faq}</section>'
            f'<p>{c["body"]}</p></main>')


def layout_list(c: dict, rng: random.Random) -> str:
    items = "".join(f'<li><a href="/y/{rng.randint(1, 9999)}">{rng.choice(WORDS).title()}</a><span>{rng.randint(1, 60)} min</span></li>' for _ in range(rng.randint(5, 15)))
    return f'<main>{c["h1"]}<p>{c["lead"]}</p><ol class="list">{items}</ol><div class="map">{_img(c["alt"], rng)}</div><p>{c["body"]}</p></main>'


def layout_product(c: dict, rng: random.Random) -> str:
    specs = "".join(f"<li>{rng.choice(WORDS)}: {rng.randint(1, 99)}</li>" for _ in range(rng.randint(4, 9)))
    reviews = "".join(f"<article><h3>{rng.randint(1, 5)} stars</h3><p>{_prose(rng, 30)}</p></article>" for _ in range(rng.randint(0, 4)))
    return (f'<main><div class="gallery">{"".join(_img(c["alt"], rng) for _ in range(4))}</div><div class="buy">{c["h1"]}'
            f'<p>{c["lead"]}</p><span class="price">${rng.randint(5, 500)}</span><button>Add to cart</button><ul class="specs">{specs}</ul></div>'
            f'<section class="reviews"><h2>Reviews</h2>{reviews}</section><p>{c["body"]}</p></main>')


def layout_job(c: dict, rng: random.Random) -> str:
    meta = "".join(f"<span>{rng.choice(WORDS)}</span>" for _ in range(4))
    bullets = "".join(f"<li>{_prose(rng, 10)}</li>" for _ in range(rng.randint(3, 8)))
    return (f'<main>{c["h1"]}<div class="meta">{meta}</div><p>{c["lead"]}</p><div class="desc"><p>{_prose(rng, 60)}</p>'
            f'<h2>Requirements</h2><ul>{bullets}</ul><p>{c["body"]}</p></div><a class="apply" href="/apply">Apply</a></main>')


LAYOUTS = {f.__name__.removeprefix("layout_"): f for f in
           (layout_profile, layout_claimed, layout_hub, layout_article, layout_person, layout_list, layout_product, layout_job)}


# --- pages ---------------------------------------------------------------------------------

def _jsonld(t: PageType, name: str, bugs: set[str], rng: random.Random) -> str:
    if "jsonld_missing" in bugs:
        return ""
    data: dict = {"@context": "https://schema.org", "@type": t.schema, "name": name}
    if t.schema in ("ApartmentComplex", "LocalBusiness"):
        data["address"] = {"@type": "PostalAddress", "streetAddress": f"{rng.randint(1, 999)} Main St", "addressLocality": "Springfield"}
    if t.schema == "Article":
        data = {"@context": "https://schema.org", "@type": "Article", "headline": name, "datePublished": "2026-10-01", "author": {"@type": "Person", "name": "Staff"}}
    if t.schema == "Product":
        data["offers"] = {"@type": "Offer", "price": rng.randint(5, 500), "priceCurrency": "USD"}
    if t.schema == "JobPosting":
        data = {"@context": "https://schema.org", "@type": "JobPosting", "title": name, "datePosted": "2026-10-01",
                "hiringOrganization": {"@type": "Organization", "name": "Acme", "url": "https://acme.test"}, "description": "Role"}
    if "jsonld_required" in bugs:
        for k in ("address", "author", "offers", "hiringOrganization", "name"):
            if k in data and k != "name":
                del data[k]
                break
        else:
            data.pop("name", None)
    if "jsonld_placeholders" in bugs:
        data["description"] = "{{entity.description}}"
    if "date_modified_missing" not in bugs:
        data["dateModified"] = "2026-10-20"
    return f'<script type="application/ld+json">{json.dumps(data)}</script>'


def make_page(site: Site, t: PageType, i: int, rng: random.Random) -> SynthPage:
    name = _name(rng)
    url = f"https://{site.host}{_fill(t.url, rng, name)}"
    bugs = {b for b, share in t.bugs.items() if share >= 1 or rng.random() < share}
    n, rent, score, k = rng.randint(20, 400), rng.randint(900, 5000), round(rng.uniform(2.5, 4.9), 1), rng.randint(3, 300)
    if t.verdict == "yes":
        lead = f"{name} is a {rng.choice(WORDS)} building with {n} units, an average rent of ${rent} and a rating of {score} out of 5 from {k} reviews."
    elif t.verdict == "decoy":
        lead = f"Call the {name} office at 555 {rng.randint(1000, 9999)} any time for leasing info and tours today."
    else:
        lead = _prose(rng, 30)
    if not t.facts_first and t.verdict != "yes":
        lead = _prose(rng, 70) + " " + lead
    if t.facts_first and t.verdict != "yes":
        lead = f"{n} units · ${rent} average rent · {score}/5. " + lead
    if "visible_placeholders" in bugs:
        lead += " -% of renters recommend this place."
    thin = "thin_content" in bugs
    c = {
        "h1": "" if "h1_missing" in bugs else f"<h1>{name}</h1>" + (f"<h1>{rng.choice(WORDS)}</h1>" if "h1_multiple" in bugs else ""),
        "lead": lead if not thin else name,
        "body": _prose(rng, 120) if not thin else "",
        "alt": "img_alt" not in bugs,
    }
    if "h1_missing" in bugs:
        c["h1"] = f'<div class="title">{name}</div>'
    main = LAYOUTS[t.layout](c, rng)
    if thin:  # strip the generated filler so the page really is thin
        main = f'<main>{c["h1"]}<p>{name} {rng.choice(WORDS)}.</p></main>'
    head = []
    if "title_missing" not in bugs:
        head.append(f"<title>{t.name.title() if 'title_duplicate' in bugs else name} | {site.name}</title>")
    if "desc_missing" not in bugs:
        head.append(f'<meta name="description" content="{name}: {_prose(rng, 18)[:140]}">')
    if "canonical_missing" not in bugs:
        head.append(f'<link rel="canonical" href="{url}">')
    head.append(_jsonld(t, name, bugs, rng))
    lang = "" if "lang_missing" in bugs else ' lang="en"'
    html = (f"<!doctype html><html{lang}><head>{''.join(head)}</head><body><header><nav><a href=\"/\">{site.name}</a>"
            f"<a href=\"/about\">About</a></nav></header>{main}<footer><p>© {site.name}</p></footer></body></html>")
    return SynthPage(url, html, t.name, bugs & set(CHECKED), t.verdict == "yes", t.facts_first or t.verdict == "yes")


def build(site: Site, seed: int) -> Site:
    rng = random.Random(seed)
    for t in site.types:
        site.pages += [make_page(site, t, i, rng) for i in range(t.count)]
    rng.shuffle(site.pages)
    return site


def sites() -> list[Site]:
    homes = Site("Nestfinder", "nestfinder.test", [
        PageType("building", "/building/{slug}", "profile", 220, {"jsonld_required": 1, "visible_placeholders": 0.5}, "yes", True, "ApartmentComplex"),
        PageType("building (claimed)", "/building/{slug}", "claimed", 90, {"desc_missing": 1, "img_alt": 1}, "decoy", True, "ApartmentComplex"),
        PageType("area", "/neighborhood/{slug}", "hub", 40, {"jsonld_missing": 1}, "no", False),
        PageType("area", "/area/{slug}", "hub", 30, {"jsonld_missing": 1}, "no", False),
        PageType("landlord", "/landlord/{id}", "person", 80, {"title_duplicate": 1, "date_modified_missing": 1}, "decoy", False, "LocalBusiness"),
        PageType("guide", "/blog/{slug}", "article", 25, {"canonical_missing": 1}, "yes", True, "Article"),
        PageType("station", "/near/{slug}", "list", 35, {"thin_content": 0.6, "lang_missing": 1}, "no", True),
    ])
    shop = Site("Gearbox", "gearbox.test", [
        PageType("product", "/p/{slug}", "product", 260, {"jsonld_placeholders": 1, "h1_multiple": 0.4}, "decoy", True, "Product"),
        PageType("category", "/c/{slug}", "hub", 45, {"desc_missing": 1}, "no", False),
        PageType("brand", "/brand/{slug}", "person", 40, {"jsonld_required": 1}, "yes", True, "LocalBusiness"),
        PageType("guide", "/guides/{date}/{slug}", "article", 30, {"title_missing": 0.5}, "yes", True, "Article"),
    ])
    jobs = Site("Hirewell", "hirewell.test", [
        PageType("job", "/jobs/{id}/{slug}", "job", 240, {"date_modified_missing": 1, "img_alt": 0.3}, "no", True, "JobPosting"),
        PageType("company", "/company/{slug}", "person", 60, {"h1_missing": 1}, "yes", True, "LocalBusiness"),
        PageType("company", "/employer/{slug}", "person", 30, {"h1_missing": 1}, "yes", True, "LocalBusiness"),
        PageType("job search", "/jobs-in/{slug}", "hub", 50, {"canonical_missing": 0.5}, "no", False),
        PageType("salary", "/salary/{slug}", "list", 40, {"visible_placeholders": 1}, "decoy", True),
    ])
    return [build(s, seed) for seed, s in enumerate([homes, shop, jobs], start=7)]
