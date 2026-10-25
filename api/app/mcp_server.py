"""MCP server: run audits from Claude Code, Cursor or any MCP client.

    claude mcp add seogeo -- uvx --from "git+https://github.com/jaylahoti/seogeo-audit-kit#subdirectory=api" seogeo-audit-mcp

Tools return compact summaries rather than whole reports, so they fit in an assistant's
context. Audits are saved, so a report can be fetched again later by its id.
"""

from __future__ import annotations

import asyncio

from mcp.server.mcpserver import MCPServer

from app.fixes.generators import generate_llms_txt as _llms
from app.pipeline.single import check_page as _check_page
from app.store import store

server = MCPServer(
    name="seogeo-audit-kit",
    title="SEOGEO Audit Kit",
    instructions=(
        "SEO and GEO (AI search) audits for programmatic sites, reported per page type (template). "
        "Use audit_site for a whole site (takes 2-4 minutes), check_page for one URL, get_page_type for the "
        "findings and ready-to-paste fixes of one page type, and get_llms_txt for a generated llms.txt."
    ),
)


def _summary(audit_id: str, r: dict) -> dict:
    return {
        "audit_id": audit_id,
        "geo": (r.get("geo") or {}).get("score"),
        "geo_partial": (r.get("geo") or {}).get("partial"),
        "seo": (r.get("scores") or {}).get("seo"),
        "ai_readiness": (r.get("scores") or {}).get("ai"),
        "visibility": (r.get("visibility") or {}).get("score"),
        "pages_estimated": (r.get("sitemap") or {}).get("urls_estimated"),
        "summary": (r.get("judge") or {}).get("summary"),
        "top_fixes": (r.get("judge") or {}).get("top_fixes", []),
        "page_types": [
            {"pattern": t["pattern"], "pages": t["estimated_pages"], "seo": t.get("seo_score"), "ai": t.get("ai_score"),
             "issues": len(t.get("findings", []))}
            for t in r.get("templates", [])[:15]
        ],
        "changes_since_last_audit": [c["title"] for c in (r.get("monitoring") or {}).get("changes", [])[:8]],
        "claude_cost_usd": (r.get("claude") or {}).get("spent"),
    }


@server.tool(description="Audit a whole site from its sitemap (2-4 minutes). Returns scores, the top fixes and page types.")
async def audit_site(url: str) -> dict:
    from app.pipeline.runner import run_audit

    if "://" not in url:
        url = f"https://{url}"
    rec = store.create(url)
    await run_audit(rec)
    if rec.status != "done":
        return {"audit_id": rec.id, "error": rec.error}
    return _summary(rec.id, rec.result)


@server.tool(description="Fetch a saved audit's summary by its id.")
async def get_report(audit_id: str) -> dict:
    rec = store.get(audit_id)
    if not rec:
        return {"error": "Audit not found"}
    if rec.status != "done":
        return {"audit_id": audit_id, "status": rec.status, "error": rec.error}
    return _summary(audit_id, rec.result)


@server.tool(description="Findings and ready-to-paste fixes (JSON-LD, verdict sentence, title) for one page type of an audit.")
async def get_page_type(audit_id: str, pattern: str) -> dict:
    rec = store.get(audit_id)
    if not rec or rec.status != "done":
        return {"error": "Audit not found or not finished"}
    t = next((t for t in rec.result.get("templates", []) if t["pattern"] == pattern), None)
    if not t:
        return {"error": "No such page type", "page_types": [x["pattern"] for x in rec.result.get("templates", [])]}
    return {
        "pattern": t["pattern"], "pages": t["estimated_pages"], "seo": t.get("seo_score"), "ai": t.get("ai_score"),
        "examples": t.get("examples", [])[:3],
        "findings": [{k: f.get(k) for k in ("id", "severity", "title", "detail", "pages", "method", "fix")} for f in t.get("findings", [])],
        "claude_page_check": (rec.result.get("claude_pages") or {}).get(t["pattern"]),
    }


@server.tool(description="Run every SEO and AI-readiness check on a single URL (seconds). Good for verifying a fix.")
async def check_page(url: str) -> dict:
    return await _check_page(url)


@server.tool(description="A generated llms.txt for an audited site, built from its page types and sitemap.")
async def get_llms_txt(audit_id: str) -> str:
    rec = store.get(audit_id)
    if not rec or rec.status != "done":
        return "Audit not found or not finished."
    return (rec.result.get("fixes") or {}).get("llms_txt") or _llms(rec.input_url, None, rec.result.get("templates", []), [])


def main() -> None:
    server.run("stdio")


if __name__ == "__main__":
    asyncio.run(server.run_stdio_async())
