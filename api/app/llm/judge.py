"""The judge: one Sonnet call per audit that ranks findings and writes the fixes.

Input is a compact digest of every page type — size, scores, findings, and what Claude's
page checks found — so the call stays small. Output is a short summary, the top fixes
across the site, and per-page-type fixes: a verdict sentence template, a title template,
and JSON-LD. Every JSON-LD fix is validated before it's shown: placeholders are filled
with dummy values, it must parse, have a schema.org @type, and include that type's
required properties. Fixes that fail validation are dropped and the reason is recorded.
"""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.checks.ai import entities, missing_required
from app.config import settings
from app.llm.client import BudgetExceeded, Claude

MAX_TEMPLATES = 10
RE_PLACEHOLDER = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")


class TopFix(BaseModel):
    page_type: str = Field(description="The URL pattern exactly as given")
    title: str = Field(description="The fix, as an instruction, under 12 words")
    why: str = Field(description="One sentence: what it changes for search or AI answers")
    effort: Literal["low", "medium", "high"]


class TemplateFix(BaseModel):
    page_type: str = Field(description="The URL pattern exactly as given")
    verdict_html: str | None = Field(description="A <p> verdict sentence template using {{field}} placeholders, or null if not needed")
    title_template: str | None = Field(description="A better <title> template using {{field}} placeholders, or null")
    jsonld: str | None = Field(description="A JSON-LD object for the page's main entity as a JSON string, values as {{field}} placeholders, or null if the page's JSON-LD is already good")
    notes: str = Field(description="One sentence on what to change in the template")


class Judgement(BaseModel):
    summary: str = Field(description="2-3 sentences for the site owner: the overall state and the single biggest opportunity")
    top_fixes: list[TopFix] = Field(description="The 5 highest-impact fixes across the site, best first, weighing pages affected × severity")
    template_fixes: list[TemplateFix] = Field(description="Fixes for the page types that need them (at most 6)")


SYSTEM = (
    "You are a senior technical SEO and GEO (generative engine optimization) lead. You review an automated "
    "audit of a programmatic site, grouped by page type (template). Prioritise by pages affected × severity. "
    "Write template-level fixes with {{field}} placeholders for the site's own data fields, not hard-coded values. "
    "Only propose JSON-LD with schema.org types that fit the page, and include every required property: for "
    "ItemList or CollectionPage list pages, give itemListElement as an array with one ListItem template "
    "({{position}}, {{url}}, {{name}}) to repeat per item. Be concrete and brief."
)


def digest(result: dict) -> str:
    templates = sorted(result.get("templates", []), key=lambda t: -t["estimated_pages"])[:MAX_TEMPLATES]
    claude = result.get("claude_pages", {})
    rows = []
    for t in templates:
        pc = claude.get(t["pattern"], {})
        rows.append({
            "page_type": t["pattern"],
            "pages": t["estimated_pages"],
            "seo_score": t.get("seo_score"),
            "ai_score": t.get("ai_score"),
            "example_title": next((s.get("title") for s in t.get("samples", []) if s.get("title")), None),
            "schema_types": sorted({x for s in t.get("samples", []) for x in s.get("schema", [])})[:10],
            "findings": [
                {"id": f["id"], "severity": f["severity"], "title": f["title"], "affected": f"{f['affected']}/{f['sampled']}", "pages": f["pages"]}
                for f in t.get("findings", [])[:8]
            ],
            "claude_page_check": {k: pc.get(k) for k in ("page_type", "facts_in_text", "facts_in_structured_data", "missing_facts", "has_verdict", "title_matches_intent", "better_title_template")} if pc else None,
        })
    site = {"geo": (result.get("geo") or {}).get("score"), "site_findings": result.get("site_findings", [])}
    return json.dumps({"site": site, "page_types": rows}, ensure_ascii=False)


def validate_jsonld(raw: str) -> tuple[bool, str]:
    """Placeholders → dummy values, then: parses, has @type, has the type's required properties."""
    filled = RE_PLACEHOLDER.sub(lambda m: "1" if re.search(r"(count|rating|units|number|price|value)", m.group(1), re.IGNORECASE) else "x", raw)
    # Numeric placeholders may sit unquoted ({{units}}); quoted ones become strings. Either way it must parse.
    try:
        data = json.loads(filled)
    except json.JSONDecodeError as e:
        return False, f"doesn't parse: {e.msg}"
    ents = entities(data)
    if not ents:
        return False, "no @type"
    missing = sorted({m for e in ents for m in missing_required(e)})
    if missing:
        return False, "missing required: " + ", ".join(missing[:4])
    return True, ""


async def judge(claude: Claude, result: dict) -> dict | None:
    try:
        res = await claude.parse(stage="judge", model=settings.judge_model, system=SYSTEM,
                                 user="Audit digest (JSON):\n" + digest(result), schema=Judgement,
                                 max_tokens=6000, effort="medium")
    except BudgetExceeded:
        return None
    if res is None:
        return None
    patterns = {t["pattern"] for t in result.get("templates", [])}
    fixes = []
    for f in res.template_fixes:
        if f.page_type not in patterns:
            continue
        entry = f.model_dump()
        if f.jsonld:
            ok, why = validate_jsonld(f.jsonld)
            entry["jsonld_valid"] = ok
            if not ok:
                entry["jsonld_rejected"] = why
                entry["jsonld"] = None
            else:
                try:  # pretty-print for display, keeping placeholders
                    entry["jsonld"] = json.dumps(json.loads(RE_PLACEHOLDER.sub(lambda m: f"__{m.group(1)}__", f.jsonld)), indent=2).replace('"__', '"{{').replace('__"', '}}"')
                except json.JSONDecodeError:
                    pass
        fixes.append(entry)
    return {
        "summary": res.summary,
        "top_fixes": [t.model_dump() for t in res.top_fixes if t.page_type in patterns][:5],
        "template_fixes": fixes,
    }
