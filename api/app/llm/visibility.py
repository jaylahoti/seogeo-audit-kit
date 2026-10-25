"""AI visibility: ask real questions with web search and see whether the site gets cited.

Questions come from Claude's page checks (what people ask about each page type), spread
across the largest page types. Each answer is classified:
  cited             — the site is a source in the answer
  found, not cited  — the site came up in the search results, but the answer used others
  not found
Visibility = 100 × (cited + 0.25 × found-not-cited) / questions. Other cited domains feed
share of voice. Question gaps combine these with whether the page itself answers.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from urllib.parse import urlsplit

from app.config import settings
from app.llm.client import BudgetExceeded, Claude

SYSTEM = (
    "Always run a web search before answering, even if you think you know the answer. "
    "Then answer the question accurately and concisely, citing the sources you used."
)


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def pick_questions(claude_pages: dict[str, dict], sizes: dict[str, int], limit: int) -> list[tuple[str, str]]:
    """Round-robin questions across page types, largest first."""
    order = sorted(claude_pages, key=lambda p: -sizes.get(p, 0))
    pools = {p: [q["question"] for q in claude_pages[p].get("questions", [])] for p in order}
    picked: list[tuple[str, str]] = []
    i = 0
    while len(picked) < limit and any(i < len(v) for v in pools.values()):
        for p in order:
            if i < len(pools[p]) and len(picked) < limit:
                picked.append((p, pools[p][i]))
        i += 1
    return picked


async def run_visibility(claude: Claude, site_url: str, claude_pages: dict[str, dict], sizes: dict[str, int]) -> dict:
    site = host(site_url)
    questions = pick_questions(claude_pages, sizes, settings.visibility_questions)
    sem = asyncio.Semaphore(3)

    async def ask(pattern: str, q: str) -> dict | None:
        async with sem:
            try:
                res = await claude.search(stage="visibility", model=settings.page_model, system=SYSTEM, question=q, max_uses=1)
            except BudgetExceeded:
                return None
        if res is None:
            return None
        cited_hosts = list(dict.fromkeys(host(u) for u in res["cited_urls"]))
        result_hosts = list(dict.fromkeys(host(u) for u in res["result_urls"]))
        cited = site in cited_hosts
        found = site in result_hosts
        return {
            "page_type": pattern,
            "question": q,
            "status": "cited" if cited else "found" if found else "missing",
            "position": cited_hosts.index(site) + 1 if cited else None,
            "cited_instead": [h for h in cited_hosts if h != site][:4],
            "answer": res["text"][:600],
        }

    answers = [a for a in await asyncio.gather(*(ask(p, q) for p, q in questions)) if a]
    if not answers:
        return {"score": None, "answers": [], "share_of_voice": [], "asked": 0,
                "reason": "No answers (budget reached or the API was unavailable)."}
    cited = sum(a["status"] == "cited" for a in answers)
    found = sum(a["status"] == "found" for a in answers)
    score = round(100 * (cited + 0.25 * found) / len(answers))

    voice = Counter()
    for a in answers:
        if a["status"] == "cited":
            voice[site] += 1
        for h in a["cited_instead"]:
            voice[h] += 1
    total = sum(voice.values()) or 1
    share = [{"domain": d, "share": round(n / total, 3), "you": d == site} for d, n in voice.most_common(6)]
    if site not in [s["domain"] for s in share]:
        share.append({"domain": site, "share": round(voice[site] / total, 3), "you": True})

    return {
        "score": score,
        "asked": len(answers),
        "cited": cited,
        "found_not_cited": found,
        "engines": [{"name": "Claude", "cited": cited, "asked": len(answers), "live": True}],
        "answers": answers,
        "share_of_voice": share,
    }


def question_gaps(claude_pages: dict[str, dict], visibility: dict) -> list[dict]:
    """Per question: does the page answer it, and does AI cite the site for it?"""
    status = {a["question"]: a["status"] for a in visibility.get("answers", [])}
    gaps = []
    for pattern, s in claude_pages.items():
        for q in s.get("questions", []):
            gaps.append({
                "page_type": pattern,
                "question": q["question"],
                "answered_on_page": q["answered"],
                "facts_extractable": s.get("facts_in_text"),
                "ai_cites_site": status.get(q["question"]),  # None = not asked
            })
    rank = {"no": 0, "partial": 1, "yes": 2}
    gaps.sort(key=lambda g: (rank[g["answered_on_page"]], g["ai_cites_site"] != "missing"))
    return gaps
