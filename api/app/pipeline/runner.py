"""The audit pipeline. Each stage emits running/done events that the UI streams live."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from urllib.parse import urlsplit

from app.checks import ai as ai_checks
from app.checks import seo as seo_checks
from app.checks.content import pick_samples
from app.checks.findings import SEVERITY_PENALTY, TemplateContext, score
from app.checks.page_facts import extract
from app.crawl.crawler import crawl
from app.ingest.llms_txt import check_llms_txt
from app.ingest.robots import fetch_robots
from app.ingest.sitemap import ingest_sitemaps
from app.ml.dom_clusters import Sampled, cluster_layouts, fingerprint, reconcile
from app.ml.url_patterns import Template, detect_url_templates
from app.net.safe_fetch import BlockedURL, check_url, make_client
from app.store import AuditRecord

# Cap concurrent audits so one busy minute can't exhaust the box.
_slots = asyncio.Semaphore(3)


def looks_like_sitemap(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return path.endswith((".xml", ".xml.gz")) or "sitemap" in path


@asynccontextmanager
async def stage(rec: AuditRecord, key: str, label: str):
    started = time.perf_counter()
    info: dict = {"detail": "", "cost": 0.0}
    await rec.emit({"type": "stage", "key": key, "label": label, "status": "running"})
    try:
        yield info
    except Exception as e:
        await rec.emit({
            "type": "stage", "key": key, "label": label, "status": "error",
            "detail": str(e), "ms": round((time.perf_counter() - started) * 1000),
        })
        raise
    await rec.emit({
        "type": "stage", "key": key, "label": label, "status": "done",
        "detail": info["detail"], "cost": info["cost"],
        "ms": round((time.perf_counter() - started) * 1000),
    })


async def run_audit(rec: AuditRecord) -> None:
    async with _slots:
        rec.status = "running"
        try:
            check_url(rec.input_url)
            async with make_client() as client:
                await _pipeline(rec, client)
            rec.status = "done"
            await rec.emit({"type": "done"})
        except BlockedURL as e:
            rec.status, rec.error = "error", str(e)
            await rec.emit({"type": "error", "message": str(e)})
        except Exception as e:  # noqa: BLE001 — top-level boundary: clean message, no traceback
            rec.status, rec.error = "error", f"Audit failed: {type(e).__name__}"
            await rec.emit({"type": "error", "message": rec.error})


async def _pipeline(rec: AuditRecord, client) -> None:
    url = rec.input_url

    async with stage(rec, "robots", "Read robots.txt") as s:
        robots = await fetch_robots(client, url)
        blocked = robots.blocked_retrieval_bots
        s["detail"] = (
            f"{len(robots.sitemaps)} sitemap(s) listed"
            + (f" · blocks {', '.join(blocked)}" if blocked else " · AI retrieval bots allowed")
            if robots.found else "No robots.txt (everything allowed)"
        )
        rec.result["robots"] = {
            "url": robots.url,
            "found": robots.found,
            "status": robots.status,
            "sitemaps": robots.sitemaps,
            "ai_crawlers": [asdict(p) for p in robots.ai_crawlers],
            "blocked_retrieval_bots": blocked,
        }

    async with stage(rec, "llms_txt", "Check llms.txt") as s:
        llms = await check_llms_txt(client, url)
        s["detail"] = (
            f"{len(llms.sections)} sections · {llms.links} links · {len(llms.issues)} issue(s)"
            if llms.found else "No /llms.txt"
        )
        rec.result["llms_txt"] = asdict(llms)

    async with stage(rec, "sitemap", "Read sitemap") as s:
        if looks_like_sitemap(url):
            start = [url]
        elif robots.sitemaps:
            start = robots.sitemaps
        else:
            p = urlsplit(url)
            start = [f"{p.scheme}://{p.netloc}/sitemap.xml"]

        async def progress(n_urls: int, n_maps: int):
            await rec.emit({"type": "progress", "key": "sitemap", "urls": n_urls, "sitemaps": n_maps})

        sm = await ingest_sitemaps(client, start, on_progress=progress)
        if not sm.urls:
            problems = "; ".join(i.message for i in sm.issues[:3]) or "no URLs listed"
            raise ValueError(f"Couldn't read any URLs from the sitemap ({problems})")
        s["detail"] = (
            f"{len(sm.sitemaps_read)} sitemap(s) · {len(sm.urls):,} URLs sampled"
            f" of ~{sm.estimated_total:,}"
        )
        rec.result["sitemap"] = {
            "start": start,
            "sitemaps_read": sm.sitemaps_read,
            "urls_sampled": len(sm.urls),
            "urls_estimated": sm.estimated_total,
            "listed_total": sm.listed_total,
            "truncated": sm.truncated,
            "off_host": sm.off_host,
            "issues": [asdict(i) for i in sm.issues],
        }

    async with stage(rec, "templates", "Detect templates (URL patterns)") as s:
        templates = detect_url_templates(sm.urls)
        s["detail"] = f"{len(templates)} templates from URL structure"
        rec.result["templates"] = [_template_json(t) for t in templates]

    async with stage(rec, "crawl", "Crawl sample pages") as s:
        to_crawl: list[tuple[int, str]] = []
        for ti, t in enumerate(templates):
            for u in _spread(t.urls, CRAWL_PER_TEMPLATE):
                to_crawl.append((ti, u.loc))
        to_crawl = to_crawl[:MAX_CRAWL]

        done = 0

        async def on_page(_page):
            nonlocal done
            done += 1
            if done % 10 == 0:
                await rec.emit({"type": "progress", "key": "crawl", "pages": done, "of": len(to_crawl)})

        pages = await crawl(client, [u for _, u in to_crawl], robots, on_page=on_page)
        ok = [p for p in pages if p.ok_html]
        blocked = sum(p.blocked_by_robots for p in pages)
        errors = sum(1 for p in pages if p.error and not p.blocked_by_robots)
        non_200 = sum(1 for p in pages if p.status and p.status != 200)
        s["detail"] = (
            f"{len(ok)} of {len(pages)} pages fetched"
            + (f" · {non_200} non-200" if non_200 else "")
            + (f" · {errors} errors" if errors else "")
            + (f" · {blocked} blocked by robots.txt" if blocked else "")
        )
        rec.result["crawl"] = {
            "requested": len(pages), "ok": len(ok), "non_200": non_200,
            "errors": errors, "blocked_by_robots": blocked,
            "avg_ms": round(sum(p.elapsed_ms for p in ok) / max(1, len(ok))),
        }

    async with stage(rec, "layouts", "Detect templates (HTML structure)") as s:
        crawled = [(ti, p) for (ti, _), p in zip(to_crawl, pages, strict=True) if p.ok_html]
        prints = await asyncio.to_thread(lambda: [fingerprint(p.html) for _, p in crawled])
        layout = await asyncio.to_thread(cluster_layouts, prints)
        samples = [
            Sampled(template=ti, url=p.url, label=lab)
            for (ti, p), lab in zip(crawled, layout.labels, strict=True)
        ]
        before = len(templates)
        templates = reconcile(templates, samples)
        n_layouts = len({lab for lab in layout.labels if lab >= 0})
        splits = sum(1 for t in templates if t.variant == 1)
        merges = sum(1 for t in templates if t.merged_from)
        s["detail"] = (
            f"MinHash + HDBSCAN on {len(crawled)} pages → {n_layouts} layouts"
            f" · {before} URL patterns → {len(templates)} templates"
            + (f" ({splits} split, {merges} merged)" if splits or merges else "")
        )
        rec.result["templates"] = [_template_json(t) for t in templates]
        rec.result["ml"] = {
            "pages": len(crawled),
            "layouts": n_layouts,
            "noise": sum(1 for lab in layout.labels if lab < 0),
            "layout_distances": layout.cluster_distances,
            "points": [
                {"x": xy[0], "y": xy[1], "layout": lab, "url": p.url}
                for (_, p), lab, xy in zip(crawled, layout.labels, layout.coords or [], strict=False)
            ],
        }


    async with stage(rec, "checks", "SEO and AI-readiness checks") as s:
        results = await asyncio.to_thread(_run_checks, templates, pages, rec.result)
        n_findings = sum(len(t["findings"]) for t in results)
        s["detail"] = (
            f"{n_findings} findings across {len(results)} templates · "
            f"SEO {rec.result['scores']['seo']} · AI readiness {rec.result['scores']['ai']}"
        )
        rec.result["templates"] = results


def _run_checks(templates: list[Template], pages: list, result: dict) -> list[dict]:
    facts = {p.url: extract(p) for p in pages if p.status is not None}
    out = []
    weights = {"seo": 0.0, "ai": 0.0, "pages": 0}
    for t in templates:
        mine = [facts[u.loc] for u in t.urls if u.loc in facts]
        lastmods = {u.loc: u.lastmod for u in t.urls}
        samples = pick_samples([f for f in mine if f.status == 200], lastmods, n=5)
        samples += [f for f in mine if f.status != 200]  # keep error pages for status checks
        ctx = TemplateContext(t.pattern, t.estimated_pages, samples, lastmods)
        findings = seo_checks.run(ctx) + ai_checks.run(ctx)
        findings.sort(key=lambda f: (-SEVERITY_PENALTY[f.severity] * f.pages))
        seo_score, ai_score = score(findings, "seo"), score(findings, "ai")
        if samples:
            weights["seo"] += seo_score * t.estimated_pages
            weights["ai"] += ai_score * t.estimated_pages
            weights["pages"] += t.estimated_pages
        out.append({
            **_template_json(t),
            "seo_score": seo_score if samples else None,
            "ai_score": ai_score if samples else None,
            "findings": [asdict(f) for f in findings],
            "passed": seo_checks.passed_checks(findings) if samples else [],
            "samples": [
                {
                    "url": f.url, "status": f.status, "words": f.word_count, "title": f.title,
                    "schema": sorted({ty for b in f.jsonld if b.data is not None for e in ai_checks.entities(b.data) for ty in ai_checks._types(e)}),
                    "ms": round(f.elapsed_ms),
                }
                for f in samples
            ],
        })
    total = max(1, weights["pages"])
    result["scores"] = {"seo": round(weights["seo"] / total), "ai": round(weights["ai"] / total)}
    result["site_findings"] = ai_checks.site_findings(result.get("robots", {}), result.get("llms_txt", {}))
    return out

CRAWL_PER_TEMPLATE = 6
MAX_CRAWL = 200


def _spread(items: list, n: int) -> list:
    if len(items) <= n:
        return items
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def _template_json(t: Template) -> dict:
    return {
        "pattern": t.pattern,
        "variant": t.variant,
        "layout": t.layout,
        "merged_from": t.merged_from,
        "estimated_pages": t.estimated_pages,
        "sampled": t.sampled,
        "has_query": t.has_query,
        "examples": [u.loc for u in t.urls[:5]],
        "lastmod_coverage": round(sum(1 for u in t.urls if u.lastmod) / max(1, t.sampled), 2),
    }
