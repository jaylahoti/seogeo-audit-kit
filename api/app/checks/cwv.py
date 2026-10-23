"""Module 3 — Core Web Vitals per template, from Google PageSpeed Insights (free).

Prefers field data (real Chrome users, p75) for the exact URL, then the origin's field
data, then the Lighthouse lab run. INP only exists in field data; the lab run reports
Total Blocking Time as its closest stand-in.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from app.checks.findings import Finding
from app.config import settings

PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
MAX_TEMPLATES = 8
CONCURRENCY = 2

# (good, poor) thresholds from web.dev
LCP = (2500, 4000)  # ms
CLS = (0.1, 0.25)
INP = (200, 500)  # ms
TBT = (200, 600)  # ms, lab only


@dataclass
class Vitals:
    url: str
    source: str  # "field-url" | "field-origin" | "lab" | "error"
    lcp_ms: float | None = None
    cls: float | None = None
    inp_ms: float | None = None
    tbt_ms: float | None = None
    performance: int | None = None  # Lighthouse 0–100
    error: str | None = None


def parse(url: str, data: dict) -> Vitals:
    v = Vitals(url=url, source="lab")
    lh = data.get("lighthouseResult", {})
    audits = lh.get("audits", {})
    score = lh.get("categories", {}).get("performance", {}).get("score")
    v.performance = round(score * 100) if isinstance(score, (int, float)) else None

    def lab(key):
        return audits.get(key, {}).get("numericValue")

    v.lcp_ms, v.cls, v.tbt_ms = lab("largest-contentful-paint"), lab("cumulative-layout-shift"), lab("total-blocking-time")

    for key, source in (("loadingExperience", "field-url"), ("originLoadingExperience", "field-origin")):
        exp = data.get(key) or {}
        metrics = exp.get("metrics") or {}
        if key == "loadingExperience" and exp.get("origin_fallback"):
            continue
        if "LARGEST_CONTENTFUL_PAINT_MS" in metrics:
            v.source = source
            v.lcp_ms = metrics["LARGEST_CONTENTFUL_PAINT_MS"].get("percentile", v.lcp_ms)
            if "CUMULATIVE_LAYOUT_SHIFT_SCORE" in metrics:
                v.cls = metrics["CUMULATIVE_LAYOUT_SHIFT_SCORE"].get("percentile", 0) / 100
            if "INTERACTION_TO_NEXT_PAINT" in metrics:
                v.inp_ms = metrics["INTERACTION_TO_NEXT_PAINT"].get("percentile")
            break
    return v


async def measure(urls: list[str]) -> list[Vitals]:
    sem = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(timeout=90) as client:

        async def one(url: str) -> Vitals:
            params = {"url": url, "strategy": "mobile", "category": "performance"}
            if settings.psi_api_key:
                params["key"] = settings.psi_api_key
            async with sem:
                try:
                    res = await client.get(PSI_URL, params=params)
                except httpx.HTTPError as e:
                    return Vitals(url=url, source="error", error=f"PageSpeed Insights unreachable ({type(e).__name__})")
            if res.status_code == 429:
                return Vitals(url=url, source="error", error="PageSpeed Insights quota reached — add a free PSI_API_KEY")
            if res.status_code != 200:
                return Vitals(url=url, source="error", error=f"PageSpeed Insights returned {res.status_code}")
            return parse(url, res.json())

        return await asyncio.gather(*(one(u) for u in urls))


def findings(v: Vitals, estimated_pages: int) -> list[Finding]:
    out: list[Finding] = []
    where = {"field-url": "real users, p75", "field-origin": "real users across the site, p75", "lab": "lab test"}.get(v.source, "")

    def add(id_, value, good_poor, title, unit, fmt):
        if value is None:
            return
        good, poor = good_poor
        if value <= good:
            return
        sev = "high" if value > poor else "medium"
        out.append(Finding(id=id_, area="seo", severity=sev, title=f"{title} {fmt(value)}{unit} ({where})",
                           detail=f"Good is {fmt(good)}{unit} or less; poor is over {fmt(poor)}{unit}. Slow pages rank lower and get crawled less.",
                           affected=1, sampled=1, pages=estimated_pages, examples=[v.url], method="psi"))

    add("cwv_lcp", v.lcp_ms, LCP, "LCP", "s", lambda x: f"{x / 1000:.1f}")
    add("cwv_cls", v.cls, CLS, "CLS", "", lambda x: f"{x:.2f}")
    add("cwv_inp", v.inp_ms, INP, "INP", "ms", lambda x: f"{x:.0f}")
    if v.inp_ms is None:
        add("cwv_tbt", v.tbt_ms, TBT, "Total Blocking Time", "ms", lambda x: f"{x:.0f}")
    return out
