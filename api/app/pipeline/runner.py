"""The audit pipeline. Each stage emits running/done events that the UI streams live."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

from app import monitoring
from app.checks import ai as ai_checks
from app.checks import geo
from app.checks import seo as seo_checks
from app.checks.content import pick_samples
from app.checks.cwv import findings as cwv_findings
from app.checks.cwv import measure
from app.checks.findings import SEVERITY_PENALTY, Finding, TemplateContext, score
from app.checks.links import check_links
from app.checks.page_facts import extract
from app.checks.render import compare, render_html
from app.checks.render import findings as render_findings
from app.config import settings
from app.crawl.crawler import crawl
from app.fixes.generators import generate_llms_txt, generate_robots_txt
from app.ingest.discover import candidate_sitemaps, discover_by_links
from app.ingest.llms_txt import check_llms_txt
from app.ingest.robots import fetch_robots
from app.ingest.sitemap import SitemapResult, ingest_sitemaps
from app.llm import page_checks
from app.llm.client import Claude
from app.llm.judge import judge
from app.llm.visibility import question_gaps, run_visibility
from app.ml.dom_clusters import Sampled, cluster_layouts, fingerprint, reconcile
from app.ml.url_patterns import Template, detect_url_templates
from app.net.safe_fetch import BlockedURL, check_url, make_client
from app.store import AuditRecord, host_of, store

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


class AuditError(Exception):
    """A problem with the site being audited; the message is shown to the user as-is."""


async def run_audit(rec: AuditRecord) -> None:
    async with _slots:
        rec.status = "running"
        try:
            check_url(rec.input_url)
            async with make_client() as client:
                await _pipeline(rec, client)
            rec.status = "done"
            store.save(rec)  # save before announcing, so the report link works immediately
            await rec.emit({"type": "done"})
        except (BlockedURL, AuditError) as e:  # expected, user-facing problems
            rec.status, rec.error = "error", str(e)
            store.save(rec)
            await rec.emit({"type": "error", "message": str(e)})
        except Exception as e:  # noqa: BLE001 — top-level boundary: clean message, no traceback
            rec.status, rec.error = "error", f"Audit failed: {type(e).__name__}"
            store.save(rec)
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
        async def progress(n_urls: int, n_maps: int):
            await rec.emit({"type": "progress", "key": "sitemap", "urls": n_urls, "sitemaps": n_maps})

        source = "sitemap"
        if looks_like_sitemap(url):
            start = [url]
        elif robots.sitemaps:
            start = robots.sitemaps
        else:
            start = candidate_sitemaps(url)[:1]
        sm = await ingest_sitemaps(client, start, on_progress=progress)
        if not sm.urls and not looks_like_sitemap(url):
            # Not listed in robots.txt or not at /sitemap.xml: try the other usual places.
            for candidate in candidate_sitemaps(url)[1:]:
                trial = await ingest_sitemaps(client, [candidate], on_progress=progress)
                if trial.urls:
                    sm, start = trial, [candidate]
                    break
        if not sm.urls:
            if looks_like_sitemap(url):
                problems = "; ".join(i.message for i in sm.issues[:2]) or "it lists no URLs"
                raise AuditError(f"Couldn't read that sitemap: {problems}.")
            # No sitemap anywhere: find pages by following links from the home page.
            await rec.emit({"type": "progress", "key": "sitemap", "urls": 0, "sitemaps": 0})
            found = await discover_by_links(client, url, robots)
            if len(found) < 2:
                raise AuditError("This site has no sitemap and its home page links to no other pages we could read.")
            sm = SitemapResult(urls=found, listed_total=len(found))
            source, start = "links", []
        s["detail"] = (
            f"No sitemap — found {len(sm.urls):,} pages by following links from the home page"
            if source == "links" else
            f"~{sm.estimated_total:,} pages, estimated from {sm.leaves_read} of {sm.leaves_total} sitemap files"
            f" · {len(sm.urls):,} URLs sampled"
            if sm.leaves_read < sm.leaves_total else
            f"{sm.estimated_total:,} pages counted from all {sm.leaves_total} sitemap file(s) · {len(sm.urls):,} URLs sampled"
        )
        rec.result["sitemap"] = {
            "source": source,
            "start": start,
            "leaves_total": sm.leaves_total,
            "leaves_read": sm.leaves_read,
            "families": [asdict(f) for f in sm.families],
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
            for u in _spread(t.urls, settings.crawl_per_template):
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
        facts = await asyncio.to_thread(lambda: {p.url: extract(p) for p in pages if p.status is not None})
        state = await asyncio.to_thread(_base_checks, templates, facts)
        s["detail"] = f"{sum(len(x.findings) for x in state)} findings across {len(state)} templates"

    origin = "{0.scheme}://{0.netloc}".format(urlsplit(url))
    async with stage(rec, "links", "Link checks (depth, broken, redirects)") as s:
        report = await check_links(client, robots, origin, [x.t.pattern for x in state], list(facts.values()))
        by_pattern = {x.t.pattern: x for x in state}
        deep = 0
        for pattern, depth in report.depth.items():
            x = by_pattern[pattern]
            if pattern in ("/", "/{static}") or not x.samples:
                continue
            if depth is None or depth > MAX_CLICKS:
                deep += 1
                x.findings.append(Finding(
                    id="deep_template", area="seo", severity="medium",
                    title=f"More than {MAX_CLICKS} clicks from the home page" if depth is None else f"{depth} clicks from the home page",
                    detail="Pages reachable only through the sitemap or deep navigation get crawled less and pass less link value. "
                           "Link to this template from hub pages, breadcrumbs or related-page modules.",
                    affected=1, sampled=1, pages=x.t.estimated_pages, method="crawl"))
        s["detail"] = (
            f"{report.bfs_pages} pages from home · {report.probed} links probed · "
            f"{len(report.broken)} broken · {len(report.redirecting)} redirecting · {deep} deep templates"
        )
        rec.result["links"] = {
            "depth": report.depth, "inbound": report.inbound, "bfs_pages": report.bfs_pages,
            "probed": report.probed, "broken": report.broken[:20], "redirecting": report.redirecting[:20],
        }

    # Rendering and PageSpeed Insights both mostly wait on the network, so run them together.
    big = [x for x in sorted(state, key=lambda x: -x.t.estimated_pages)
           if x.t.pattern not in ("/", "/{static}") and any(f.status == 200 for f in x.samples)]

    async def render_stage():
        async with stage(rec, "render", "What AI sees (with vs without JavaScript)") as s:
            if not settings.render_pages:
                s["detail"] = "Skipped (render_pages is off)"
                rec.result["render"] = []
                return
            picks = [(x, next(f for f in x.samples if f.status == 200)) for x in big[:MAX_RENDER]]
            html = await render_html([f.url for _, f in picks], robots)
            diffs = []
            for x, f in picks:
                d = compare(f, html.get(f.url))
                diffs.append({"pattern": x.t.pattern, **asdict(d), "js_text_share": round(d.js_text_share, 3)})
                x.findings.extend(render_findings(d, x.t.estimated_pages))
            hidden = [d for d in diffs if d["js_text_share"] >= 0.2]
            s["detail"] = f"{len(diffs)} templates rendered · {len(hidden)} need JavaScript for 20%+ of their text"
            rec.result["render"] = diffs

    async def cwv_stage():
        async with stage(rec, "cwv", "Core Web Vitals (PageSpeed Insights)") as s:
            picks = [(x, next(f for f in x.samples if f.status == 200)) for x in big[:MAX_CWV]]
            vitals = await measure([f.final_url for _, f in picks])
            for (x, _), v in zip(picks, vitals, strict=True):
                x.findings.extend(cwv_findings(v, x.t.estimated_pages))
            errors = [v.error for v in vitals if v.error]
            s["detail"] = f"{len(vitals) - len(errors)} of {len(vitals)} templates measured" + (f" · {errors[0]}" if errors else "")
            rec.result["cwv"] = [{"pattern": x.t.pattern, **asdict(v)} for (x, _), v in zip(picks, vitals, strict=True)]

    await asyncio.gather(render_stage(), cwv_stage())

    claude = Claude()
    sizes = {x.t.pattern: x.t.estimated_pages for x in state}

    async with stage(rec, "claude_pages", "Claude page checks (facts, verdict, title)") as s:
        if not claude.enabled:
            s["detail"] = "Skipped: no ANTHROPIC_API_KEY (rule heuristics used instead)"
        else:
            picks = [x for x in big if x.t.pattern not in ("/", "/{static}")][: settings.claude_templates]
            jobs = [(x.t.pattern, f) for x in picks for f in x.samples if f.status == 200]
            checks = await page_checks.check_pages(claude, jobs)
            summaries = {}
            for x in picks:
                cs = checks.get(x.t.pattern)
                if not cs:
                    continue
                summaries[x.t.pattern] = page_checks.summarize(cs)
                ctx = TemplateContext(x.t.pattern, x.t.estimated_pages, x.samples, {})
                claude_findings = page_checks.findings(ctx, cs, [f for f in x.samples if f.status == 200])
                # Claude's judgement replaces the quick heuristics for the same questions.
                x.findings = [f for f in x.findings if f.id not in ("no_verdict", "facts_buried")] + claude_findings
            rec.result["claude_pages"] = summaries
            st = claude.ledger.for_stage("claude_pages")
            s["cost"] = st["cost"]
            s["detail"] = f"{len(jobs)} pages across {len(summaries)} page types · {st['calls']} Haiku calls · ${st['cost']:.3f}"

    async with stage(rec, "visibility", "AI visibility (Claude with web search)") as s:
        if not claude.enabled or not rec.result.get("claude_pages"):
            s["detail"] = "Skipped: needs Claude page checks"
        else:
            vis = await run_visibility(claude, url, rec.result["claude_pages"], sizes)
            rec.result["visibility"] = vis
            rec.result["question_gaps"] = question_gaps(rec.result["claude_pages"], vis)
            st = claude.ledger.for_stage("visibility")
            s["cost"] = st["cost"]
            s["detail"] = (
                f"{vis.get('asked', 0)} questions · cited in {vis.get('cited', 0)} · found but not cited in "
                f"{vis.get('found_not_cited', 0)} · {st['searches']} searches · ${st['cost']:.3f}"
            )

    async with stage(rec, "score", "Score and generate fixes") as s:
        rec.result["templates"] = _finalize(state, rec.result)
        rec.result["geo"] = geo.compute(rec.result)
        sitemaps = rec.result["sitemap"]["start"] if rec.result.get("sitemap") else []
        rec.result["fixes"] = {
            "llms_txt": generate_llms_txt(origin, report.home, rec.result["templates"], sitemaps),
            "robots_txt": generate_robots_txt(rec.result.get("robots", {}), sitemaps),
        }
        n = sum(len(t["findings"]) for t in rec.result["templates"])
        g = rec.result["geo"]
        s["detail"] = (
            f"{n} findings · GEO {g['score']}{' (partial)' if g['partial'] else ''} · SEO {rec.result['scores']['seo']}"
            f" · AI readiness {rec.result['scores']['ai']}"
        )

    async with stage(rec, "judge", "Judge and write fixes (Claude Sonnet)") as s:
        if not claude.enabled:
            s["detail"] = "Skipped: no ANTHROPIC_API_KEY"
        else:
            verdict = await judge(claude, rec.result)
            if verdict:
                rec.result["judge"] = verdict
                _attach_fixes(rec.result["templates"], verdict["template_fixes"])
            st = claude.ledger.for_stage("judge")
            s["cost"] = st["cost"]
            valid = sum(1 for f in (verdict or {}).get("template_fixes", []) if f.get("jsonld"))
            s["detail"] = (f"Summary, {len(verdict['top_fixes'])} top fixes, fixes for {len(verdict['template_fixes'])} page types "
                           f"({valid} JSON-LD validated) · ${st['cost']:.3f}") if verdict else "The judge didn't return a result"

    monitoring.attach(rec.id, host_of(url), rec.result)
    rec.result["claude"] = claude.ledger.to_json()
    rec.result["naive_cost_usd"] = round(sum(sizes.values()) * NAIVE_COST_PER_PAGE, 2)


# What it would cost to send every page through Sonnet (~3K tokens in, 500 out): the
# "naive" comparison shown next to the real audit cost.
NAIVE_COST_PER_PAGE = 3000 * 2.0 / 1e6 + 500 * 10.0 / 1e6

FIX_TARGETS = {
    "jsonld": ("jsonld", "JSON-LD for this page type", {"jsonld_missing", "jsonld_required", "jsonld_placeholders", "jsonld_no_entity", "facts_not_extractable"}),
    "verdict_html": ("html", "Verdict sentence", {"no_verdict", "visible_placeholders"}),
    "title_template": ("html", "Title template", {"title_intent", "title_long", "title_short", "title_duplicate"}),
}


def _attach_fixes(templates: list[dict], fixes: list[dict]) -> None:
    """Put each judge-written fix on the finding it resolves (first match per fix)."""
    by_pattern = {t["pattern"]: t for t in templates}
    for fix in fixes:
        t = by_pattern.get(fix["page_type"])
        if not t:
            continue
        t["judge_notes"] = fix.get("notes")
        for key, (kind, label, ids) in FIX_TARGETS.items():
            content = fix.get(key)
            if not content:
                continue
            target = next((f for f in t["findings"] if f["id"] in ids and "fix" not in f), None)
            if target:
                target["fix"] = {"kind": kind, "label": label, "content": content}


MAX_CLICKS = 3
MAX_RENDER = 12
MAX_CWV = 8


@dataclass
class _TemplateState:
    t: Template
    samples: list
    findings: list[Finding] = field(default_factory=list)


def _base_checks(templates: list[Template], facts: dict) -> list[_TemplateState]:
    out = []
    for t in templates:
        mine = [facts[u.loc] for u in t.urls if u.loc in facts]
        lastmods = {u.loc: u.lastmod for u in t.urls}
        samples = pick_samples([f for f in mine if f.status == 200], lastmods, n=settings.samples_per_template)
        samples += [f for f in mine if f.status != 200]  # keep error pages for status checks
        ctx = TemplateContext(t.pattern, t.estimated_pages, samples, lastmods)
        out.append(_TemplateState(t, samples, seo_checks.run(ctx) + ai_checks.run(ctx)))
    return out


def _finalize(state: list[_TemplateState], result: dict) -> list[dict]:
    out = []
    weights = {"seo": 0.0, "ai": 0.0, "pages": 0}
    for x in state:
        t, samples, findings = x.t, x.samples, x.findings
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
    links = result.get("links", {})
    if links.get("broken"):
        result["site_findings"].append({"id": "broken_links", "severity": "high",
            "title": f"{len(links['broken'])} broken internal links (of {links['probed']} checked)",
            "detail": "Links on your pages that return 4xx/5xx: " + ", ".join(b["target"] for b in links["broken"][:3])})
    chains = [r for r in links.get("redirecting", []) if r.get("found_on")]
    if chains:
        result["site_findings"].append({"id": "links_to_redirects", "severity": "low",
            "title": f"{len(chains)} internal links point at redirects",
            "detail": "Link straight to the final URL: " + ", ".join(f"{r['target']} → {r['to']}" for r in chains[:3])})
    return out


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
