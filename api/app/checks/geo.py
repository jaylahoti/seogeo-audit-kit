"""GEO score: how well AI search can find, read and cite the site.

  Access     — can AI bots reach and read the pages? (robots.txt policy, llms.txt,
               content that needs JavaScript, click depth)
  Readiness  — can AI understand and quote them? (the AI-readiness checks per template)
  Visibility — does AI actually cite the site? (citation checks with web search; Claude)

GEO = Access 30% + Readiness 40% + Visibility 30%. Parts that haven't run yet are left out
and the weights renormalised, and the score is marked partial so the UI can say so.
Every Access deduction is listed as a signal, so the number is explainable.
"""

from __future__ import annotations

WEIGHTS = {"access": 0.3, "readiness": 0.4, "visibility": 0.3}


def _weighted(values: list[tuple[float, int]]) -> float:
    total = sum(w for _, w in values)
    return sum(v * w for v, w in values) / total if total else 0.0


def access_score(robots: dict, llms: dict, render: list[dict], templates: list[dict], links: dict) -> dict:
    signals: list[dict] = []

    def deduct(points: float, label: str, detail: str):
        if points >= 0.5:
            signals.append({"label": label, "detail": detail, "impact": -round(points)})

    blocked = robots.get("blocked_retrieval_bots") or []
    deduct(min(50, 25 * len(blocked)), f"robots.txt blocks {', '.join(blocked)}" if blocked else "",
           "Retrieval bots fetch pages to answer live questions; blocking them removes the site from those answers.")

    if not llms.get("found"):
        deduct(10, "No /llms.txt", "A short guide for AI assistants to the site and its key pages.")
    elif llms.get("issues"):
        deduct(5, "llms.txt has problems", "; ".join(llms["issues"][:2]))

    pages = {t["pattern"]: t["estimated_pages"] for t in templates}
    failed = [d["pattern"] for d in render if d.get("error")]
    if failed:
        # Not a deduction: we couldn't measure these, so say so rather than score them as fine.
        signals.append({"label": f"{len(failed)} template(s) couldn't be rendered", "impact": 0,
                        "detail": "JavaScript-only content wasn't measured for " + ", ".join(failed[:3])
                                  + ". Access may be lower than shown; re-run to try again."})
    rendered = [(d, pages.get(d["pattern"], 1)) for d in render if not d.get("error")]
    if rendered:
        js_share = _weighted([(d["js_text_share"], w) for d, w in rendered])
        worst = max(rendered, key=lambda x: x[0]["js_text_share"])[0]
        deduct(40 * js_share, f"{js_share:.0%} of text needs JavaScript (weighted by pages)",
               f"Most AI crawlers don't run JavaScript. Worst: {worst['pattern']} at {worst['js_text_share']:.0%}.")
        js_ld = _weighted([(1.0 if d["rendered_jsonld"] > d["raw_jsonld"] == 0 else 0.0, w) for d, w in rendered])
        deduct(15 * js_ld, "JSON-LD added by JavaScript", "Structured data that only appears after scripts run is invisible to most AI crawlers.")

    depth = links.get("depth") or {}
    sized = [(1.0 if (depth.get(p) is None or depth.get(p) > 3) else 0.0, n)
             for p, n in pages.items() if p not in ("/", "/{static}") and p in depth]
    if sized:
        deep = _weighted(sized)
        deduct(15 * deep, f"{deep:.0%} of pages more than 3 clicks from home",
               "Deep pages get crawled less often by every bot, AI bots included.")

    score = max(0, round(100 + sum(s["impact"] for s in signals)))
    return {"score": score, "signals": signals, "unmeasured": failed}


def readiness_score(templates: list[dict]) -> dict:
    scored = [(t["ai_score"], t["estimated_pages"]) for t in templates if t.get("ai_score") is not None]
    return {"score": round(_weighted(scored)) if scored else None, "method": "rules"}


def geo_score(access: dict, readiness: dict, visibility: dict) -> dict:
    parts = {"access": access.get("score"), "readiness": readiness.get("score"), "visibility": visibility.get("score")}
    available = {k: v for k, v in parts.items() if v is not None}
    if not available:
        return {"score": None, "partial": True}
    # Visibility from few searched answers is noisy, so it counts in proportion to its sample.
    weights = {k: WEIGHTS[k] * (visibility.get("confidence", 1.0) if k == "visibility" else 1.0) for k in available}
    score = round(sum(v * weights[k] for k, v in available.items()) / sum(weights.values()))
    return {"score": score, "partial": len(available) < len(parts), "weights": weights}


def compute(result: dict) -> dict:
    access = access_score(result.get("robots", {}), result.get("llms_txt", {}), result.get("render", []),
                          result.get("templates", []), result.get("links", {}))
    readiness = readiness_score(result.get("templates", []))
    vis = result.get("visibility") or {}
    if vis.get("score") is not None:
        visibility = {"score": vis["score"], "engines": vis.get("engines", []), "asked": vis.get("asked"),
                      "confidence": vis.get("confidence", 1.0)}
    else:
        visibility = {"score": None, "status": "pending",
                      "reason": vis.get("reason") or "Needs AI citation checks (Claude with web search)."}
    if result.get("claude_pages"):
        readiness["method"] = "rules + claude"
    return {**geo_score(access, readiness, visibility), "access": access, "readiness": readiness, "visibility": visibility}
