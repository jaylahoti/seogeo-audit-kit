"""Run the evals on the synthetic sites and write the scores.

    uv run python -m evals.run                     # offline: page types + rule checks + heuristics
    uv run python -m evals.run --claude            # also Claude's page checks (~$0.03 of Haiku)
    Results go to web/lib/evals.json, which the ML Lab shows.

What is measured:
  page types   adjusted Rand index (ARI) of the pages the audit read vs the true types, for URL
               patterns alone and for URL patterns + page structure (the shipped method); and the
               error in estimated pages per type.
  rule checks  per page type and check: did the check fire, was the bug really there?
               precision / recall / F1 over the checks whose truth the generator controls.
  summaries    "is there a quotable summary sentence?" and "are key facts up front?" on each sample
               page: the quick heuristic vs Claude, each against the truth (accuracy, Cohen's kappa).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

from sklearn.metrics import adjusted_rand_score, cohen_kappa_score

from app.checks.ai import facts_up_front, has_verdict
from app.checks.page_facts import extract
from app.config import settings
from app.crawl.crawler import Page
from app.ingest.sitemap import SitemapURL
from app.ml.dom_clusters import Sampled, cluster_layouts, fingerprint, reconcile
from app.ml.url_patterns import detect_url_templates
from app.pipeline.runner import _base_checks, _spread
from evals.synth import CHECKED, Site, sites


def _majority(labels: list[str]) -> str:
    return Counter(labels).most_common(1)[0][0]


def eval_site(site: Site) -> tuple[dict, list[dict], list[dict]]:
    by_url = {p.url: p for p in site.pages}
    templates = detect_url_templates([SitemapURL(p.url, lastmod="2026-10-20") for p in site.pages])

    picked: list[tuple[int, str]] = [(ti, u.loc) for ti, t in enumerate(templates) for u in _spread(t.urls, settings.crawl_per_template)]
    pages = [Page(url=u, final_url=u, status=200, content_type="text/html", html=by_url[u].html, elapsed_ms=120) for _, u in picked]
    layout = cluster_layouts([fingerprint(p.html) for p in pages])
    url_only = {u: ti for ti, u in picked}
    final = reconcile(templates, [Sampled(template=ti, url=u, label=lab) for (ti, u), lab in zip(picked, layout.labels, strict=True)])
    final_of = {u.loc: i for i, t in enumerate(final) for u in t.urls}

    read = [u for _, u in picked]
    truth = [by_url[u].label for u in read]
    ari_url = adjusted_rand_score(truth, [url_only[u] for u in read])
    ari = adjusted_rand_score(truth, [final_of[u] for u in read])

    # Estimated pages per true type: the type's majority template, vs its true size.
    true_size = Counter(p.label for p in site.pages)
    est_by_label: Counter = Counter()
    for i, t in enumerate(final):
        mine = [by_url[u].label for u in read if final_of[u] == i]
        if mine:
            est_by_label[_majority(mine)] += t.estimated_pages
    count_err = sum(abs(est_by_label[k] - n) / n for k, n in true_size.items()) / len(true_size)

    # Rule checks per final template, against the bugs its true type really has.
    facts = {p.url: extract(p) for p in pages}
    state = _base_checks(final, facts)
    rows = []
    for x in state:
        labels = [by_url[f.url].label for f in x.samples]
        if not labels:
            continue
        label = _majority(labels)
        has = set().union(*(p.bugs for p in site.pages if p.label == label))
        fired = {f.id for f in x.findings}
        for cid in CHECKED:
            rows.append({"site": site.name, "page_type": label, "check": cid, "truth": cid in has, "fired": cid in fired})

    samples = [{"pattern": x.t.pattern, "facts": f, "truth_verdict": by_url[f.url].verdict, "truth_facts": by_url[f.url].facts_first}
               for x in state for f in x.samples]
    summary = {
        "name": site.name, "pages": len(site.pages), "true_types": len(true_size), "found_types": len(final),
        "pages_read": len(read), "ari_url_only": round(ari_url, 3), "ari": round(ari, 3), "count_error": round(count_err, 3),
    }
    return summary, rows, samples


def _prf(rows: list[dict]) -> dict:
    tp = sum(r["truth"] and r["fired"] for r in rows)
    fp = sum(r["fired"] and not r["truth"] for r in rows)
    fn = sum(r["truth"] and not r["fired"] for r in rows)
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r) if p + r else 0, 3)}


def _agree(truth: list[bool], pred: list[bool]) -> dict:
    acc = sum(a == b for a, b in zip(truth, pred, strict=True)) / len(truth)
    kappa = cohen_kappa_score(truth, pred) if len(set(truth)) > 1 else float("nan")
    return {"n": len(truth), "accuracy": round(acc, 3), "kappa": round(float(kappa), 3)}


async def _claude_scores(samples: list[dict], limit: int) -> dict | None:
    from app.llm import page_checks
    from app.llm.client import Claude

    claude = Claude(budget=0.25)
    if not claude.enabled:
        return None
    # Spread the budget across page types.
    by_type: dict[str, list[dict]] = {}
    for s in samples:
        by_type.setdefault(s["pattern"] + s["facts"].url.split("/")[2], []).append(s)
    chosen: list[dict] = []
    while len(chosen) < limit and any(by_type.values()):
        for v in by_type.values():
            if v and len(chosen) < limit:
                chosen.append(v.pop(0))
    checks = await page_checks.check_pages(claude, [(s["pattern"], s["facts"]) for s in chosen])
    # check_pages groups by pattern in order; line results back up with their pages.
    queue = {k: list(v) for k, v in checks.items()}
    truth_v, pred_v, truth_f, pred_f, heur_v, heur_f = [], [], [], [], [], []
    for s in chosen:
        got = queue.get(s["pattern"])
        if not got:
            continue
        c = got.pop(0)
        truth_v.append(s["truth_verdict"]); pred_v.append(c.verdict_sentence is not None)
        truth_f.append(s["truth_facts"]); pred_f.append(c.facts_up_front)
        heur_v.append(has_verdict(s["facts"])); heur_f.append(facts_up_front(s["facts"]))
    if not truth_v:
        return None
    return {"verdict": _agree(truth_v, pred_v), "facts_first": _agree(truth_f, pred_f),
            # The heuristic on exactly the same pages, for a like-for-like comparison.
            "heuristic_same_pages": {"verdict": _agree(truth_v, heur_v), "facts_first": _agree(truth_f, heur_f)},
            "cost_usd": round(claude.ledger.spent, 4), "calls": len(claude.ledger.calls), "model": settings.page_model}


def run(with_claude: bool = False, claude_pages: int = 40) -> dict:
    summaries, rows, samples = [], [], []
    for site in sites():
        s, r, smp = eval_site(site)
        summaries.append(s); rows += r; samples += smp

    per_check = {cid: _prf([r for r in rows if r["check"] == cid]) for cid in CHECKED}
    heur_v = _agree([s["truth_verdict"] for s in samples], [has_verdict(s["facts"]) for s in samples])
    heur_f = _agree([s["truth_facts"] for s in samples], [facts_up_front(s["facts"]) for s in samples])
    claude = asyncio.run(_claude_scores(samples, claude_pages)) if with_claude else None

    n = sum(s["pages_read"] for s in summaries)
    return {
        "generated_at": time.time(),
        "dataset": f"{len(summaries)} synthetic sites, {sum(s['pages'] for s in summaries)} pages, {sum(s['true_types'] for s in summaries)} true page types",
        "sites": summaries,
        "page_types": {
            "ari": round(sum(s["ari"] * s["pages_read"] for s in summaries) / n, 3),
            "ari_url_only": round(sum(s["ari_url_only"] * s["pages_read"] for s in summaries) / n, 3),
            "count_error": round(sum(s["count_error"] for s in summaries) / len(summaries), 3),
        },
        "checks": {**_prf(rows), "per_check": per_check},
        "summaries": {"heuristic": {"verdict": heur_v, "facts_first": heur_f}, "claude": claude},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--claude", action="store_true", help="also score Claude's page checks (uses ANTHROPIC_API_KEY)")
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[2] / "web" / "lib" / "evals.json")
    a = ap.parse_args(argv)
    res = run(with_claude=a.claude)
    if not a.claude and a.out.exists():  # keep the last Claude scores when re-running offline
        prev = json.loads(a.out.read_text())
        res["summaries"]["claude"] = prev.get("summaries", {}).get("claude")
    a.out.write_text(json.dumps(res, indent=2) + "\n")
    pt, ck, sm = res["page_types"], res["checks"], res["summaries"]
    print(res["dataset"])
    print(f"page types   ARI {pt['ari']}  (URL patterns alone {pt['ari_url_only']})  page-count error {pt['count_error']:.1%}")
    print(f"rule checks  precision {ck['precision']}  recall {ck['recall']}  F1 {ck['f1']}")
    print(f"summary sentence  heuristic acc {sm['heuristic']['verdict']['accuracy']} κ {sm['heuristic']['verdict']['kappa']}"
          + (f"  ·  Claude acc {sm['claude']['verdict']['accuracy']} κ {sm['claude']['verdict']['kappa']}" if sm["claude"] else ""))
    print(f"facts first       heuristic acc {sm['heuristic']['facts_first']['accuracy']}"
          + (f"  ·  Claude acc {sm['claude']['facts_first']['accuracy']}" if sm["claude"] else ""))
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
