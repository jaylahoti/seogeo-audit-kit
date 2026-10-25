"""Command-line tool, also used by the GitHub Action.

    seogeo-audit audit example.com                      # full audit, prints a summary
    seogeo-audit audit example.com --fail-on "geo<60,high-issues>0,missing-jsonld"
    seogeo-audit audit example.com --json report.json --summary $GITHUB_STEP_SUMMARY
    seogeo-audit page https://example.com/some/page     # check one page

Exit codes: 0 ok, 1 a --fail-on rule failed, 2 the audit itself failed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys

from app.config import settings

RULE = re.compile(r"^(geo|seo|ai|visibility)\s*<\s*(\d+)$|^high-issues\s*>\s*(\d+)$|^missing-jsonld$")


def parse_rules(spec: str) -> list[str]:
    rules = [r.strip() for r in spec.split(",") if r.strip()]
    for r in rules:
        if not RULE.match(r):
            raise SystemExit(f"Unknown --fail-on rule: {r!r}. Use geo<N, seo<N, ai<N, visibility<N, high-issues>N or missing-jsonld.")
    return rules


def evaluate(result: dict, rules: list[str]) -> list[str]:
    """Return the rules that fail, each with the value that failed it."""
    scores = {
        "geo": (result.get("geo") or {}).get("score"),
        "seo": (result.get("scores") or {}).get("seo"),
        "ai": (result.get("scores") or {}).get("ai"),
        "visibility": (result.get("visibility") or {}).get("score"),
    }
    templates = result.get("templates", [])
    failed = []
    for r in rules:
        m = RULE.match(r)
        if m.group(1):
            value = scores[m.group(1)]
            if value is not None and value < int(m.group(2)):
                failed.append(f"{r} (was {value})")
        elif m.group(3) is not None:
            highs = sum(1 for t in templates for f in t.get("findings", []) if f["severity"] == "high")
            if highs > int(m.group(3)):
                failed.append(f"{r} (was {highs})")
        else:
            missing = [t["pattern"] for t in templates if any(f["id"] == "jsonld_missing" for f in t.get("findings", []))]
            if missing:
                failed.append(f"missing-jsonld ({', '.join(missing[:3])})")
    return failed


def summary_markdown(result: dict, failed: list[str], url: str) -> str:
    geo = result.get("geo") or {}
    s = result.get("scores") or {}
    lines = [f"## SEOGEO Audit Kit — {url}", "",
             (f"**GEO {geo.get('score', '—')}**{' (partial)' if geo.get('partial') else ''} · SEO {s.get('seo', '—')} · "
             f"AI readiness {s.get('ai', '—')} · {len(result.get('templates', []))} page types"), ""]
    if result.get("judge"):
        lines += [result["judge"]["summary"], "", "**Top fixes**", ""]
        lines += [f"- `{f['page_type']}` — {f['title']}" for f in result["judge"]["top_fixes"]]
        lines.append("")
    changes = [c for c in (result.get("monitoring") or {}).get("changes", []) if c["kind"] != "fixed"]
    if changes:
        lines += ["**Since the last audit**", ""] + [f"- [{c['severity']}] {c['title']}" for c in changes[:8]] + [""]
    lines.append(("**Failed:** " + "; ".join(failed)) if failed else "All checks passed.")
    cost = (result.get("claude") or {}).get("spent")
    if cost is not None:
        lines.append(f"\n<sub>Claude cost: ${cost:.3f}</sub>")
    return "\n".join(lines) + "\n"


async def _audit(url: str) -> dict:
    from app.pipeline.runner import run_audit
    from app.store import store

    if "://" not in url:
        url = f"https://{url}"
    rec = store.create(url)
    task = asyncio.create_task(run_audit(rec))
    shown = 0
    while not task.done():
        await asyncio.sleep(0.5)
        for e in rec.events[shown:]:
            if e.get("type") == "stage" and e.get("status") in ("done", "error"):
                print(f"  {'✓' if e['status'] == 'done' else '✕'} {e['label']}: {e.get('detail', '')}", file=sys.stderr)
        shown = len(rec.events)
    await task
    if rec.status != "done":
        raise SystemExit(f"Audit failed: {rec.error}")
    return {"id": rec.id, **rec.result}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="seogeo-audit", description="SEO and GEO audits for programmatic sites, per page type.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit", help="Audit a whole site from its sitemap")
    a.add_argument("url")
    a.add_argument("--fail-on", default="", help='Comma-separated rules, e.g. "geo<60,high-issues>0,missing-jsonld"')
    a.add_argument("--json", help="Write the full result as JSON to this file")
    a.add_argument("--summary", help="Append a Markdown summary to this file (e.g. $GITHUB_STEP_SUMMARY)")
    a.add_argument("--max-cost", type=float, help="Claude budget in USD for this audit")
    a.add_argument("--no-render", action="store_true", help="Skip the headless-browser step (faster in CI)")
    p = sub.add_parser("page", help="Check a single page")
    p.add_argument("url")
    args = ap.parse_args(argv)

    if args.cmd == "page":
        from app.pipeline.single import check_page

        print(json.dumps(asyncio.run(check_page(args.url)), indent=2))
        return 0

    rules = parse_rules(args.fail_on)
    if args.max_cost is not None:
        settings.max_audit_cost_usd = args.max_cost
    if args.no_render:
        settings.render_pages = False
    try:
        result = asyncio.run(_audit(args.url))
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    failed = evaluate(result, rules)
    md = summary_markdown(result, failed, args.url)
    print(md)
    if args.json:
        with open(args.json, "w") as fh:
            json.dump(result, fh, indent=2, default=str)
    if args.summary:
        with open(args.summary, "a") as fh:
            fh.write(md)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
