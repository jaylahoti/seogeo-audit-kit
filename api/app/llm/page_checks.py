"""Claude page checks: one Haiku call per sample page.

Answers what rules can't:
  * which key facts a page of this type should state, and whether this page states them
    in its text and in its structured data (the fact-extraction test);
  * whether there's one quotable verdict sentence, and whether key facts come first;
  * whether the title matches how people ask about this kind of page;
  * which questions people ask that this page type should answer, and whether it does.

Results are aggregated per page type and replace the rule heuristics for verdict and
facts-up-front (method "claude").
"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from pydantic import BaseModel, Field

from app.checks.findings import Finding, TemplateContext, make
from app.checks.page_facts import PageFacts
from app.config import settings
from app.llm.client import BudgetExceeded, Claude

MAX_TEXT_CHARS = 6000
MAX_JSONLD_CHARS = 2500


class Fact(BaseModel):
    name: str = Field(description="A key fact someone would want from a page of this type, e.g. 'rent range'")
    value: str | None = Field(description="The value as stated on the page, or null if not stated")
    in_text: bool = Field(description="Stated explicitly in the visible text")
    in_structured_data: bool = Field(description="Present in the JSON-LD")


class Question(BaseModel):
    question: str = Field(description="A real question people ask that this page should answer, about this page's subject")
    answered: Literal["yes", "partial", "no"]


class PageCheck(BaseModel):
    page_type: str = Field(description="What kind of page this is, in 2-4 words, e.g. 'apartment building profile'")
    facts: list[Fact] = Field(description="5 to 8 key facts for this page type")
    verdict_sentence: str | None = Field(description="Quote the one self-contained sentence an AI answer could lift to sum up the subject, or null if there isn't one")
    facts_up_front: bool = Field(description="The most important facts appear in the first ~100 words")
    title_matches_intent: bool = Field(description="The title fits how people actually search for this subject")
    better_title_template: str | None = Field(description="If not, a better title pattern using {placeholders}, else null")
    questions: list[Question] = Field(description="3 to 4 questions people ask about this page's subject")


SYSTEM = (
    "You audit web pages for how well AI search assistants can read and quote them. "
    "Judge only from the page content given. Be strict: a fact counts as in_text only if its value is "
    "explicitly stated (not a placeholder like '-%', 'N/A', or an empty widget). Keep facts specific to "
    "what visitors of this page type care about."
)


def _jsonld_excerpt(p: PageFacts) -> str:
    blocks = [b.data for b in p.jsonld if b.data is not None]
    raw = json.dumps(blocks, ensure_ascii=False)
    return raw[:MAX_JSONLD_CHARS] + ("…" if len(raw) > MAX_JSONLD_CHARS else "")


def prompt(p: PageFacts, pattern: str) -> str:
    headings = "\n".join(f"{'#' * lvl} {t}" for lvl, t in p.headings[:25])
    return (
        f"URL pattern (page type): {pattern}\nURL: {p.url}\nTitle: {p.title}\nMeta description: {p.meta_description}\n\n"
        f"Headings:\n{headings}\n\nVisible text (first {MAX_TEXT_CHARS} chars):\n{p.main_text[:MAX_TEXT_CHARS]}\n\n"
        f"JSON-LD:\n{_jsonld_excerpt(p) or 'none'}"
    )


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def grounded(check: PageCheck, page: PageFacts) -> PageCheck:
    """Drop a verdict quote that isn't actually on the page (guards against invented quotes)."""
    if check.verdict_sentence:
        quote = _norm(check.verdict_sentence).strip(" .\"'“”")
        body = _norm(page.main_text)
        # Accept the quote if its opening and closing stretches both appear verbatim.
        head, tail = quote[:50], quote[-40:]
        if not (head in body and tail in body):
            check = check.model_copy(update={"verdict_sentence": None})
    return check


async def check_pages(claude: Claude, jobs: list[tuple[str, PageFacts]]) -> dict[str, list[PageCheck]]:
    """jobs: (pattern, page). Returns pattern -> checks. Stops quietly when the budget runs out."""
    out: dict[str, list[PageCheck]] = {}
    sem = asyncio.Semaphore(4)

    async def one(pattern: str, page: PageFacts):
        async with sem:
            try:
                res = await claude.parse(stage="claude_pages", model=settings.page_model, system=SYSTEM,
                                         user=prompt(page, pattern), schema=PageCheck, max_tokens=2500, effort="low")
            except BudgetExceeded:
                return
            if res:
                out.setdefault(pattern, []).append(grounded(res, page))

    await asyncio.gather(*(one(t, p) for t, p in jobs))
    return out


def summarize(checks: list[PageCheck]) -> dict:
    facts = [f for c in checks for f in c.facts]
    in_text = sum(f.in_text for f in facts) / len(facts) if facts else None
    in_ld = sum(f.in_structured_data for f in facts) / len(facts) if facts else None
    missing: dict[str, int] = {}
    for f in facts:
        if not f.in_text:
            missing[f.name.lower()] = missing.get(f.name.lower(), 0) + 1
    qs = [q for c in checks for q in c.questions]
    return {
        "page_type": checks[0].page_type if checks else None,
        "pages": len(checks),
        "facts_in_text": round(in_text, 3) if in_text is not None else None,
        "facts_in_structured_data": round(in_ld, 3) if in_ld is not None else None,
        "missing_facts": [name for name, _ in sorted(missing.items(), key=lambda x: -x[1])][:5],
        "verdicts": [c.verdict_sentence for c in checks if c.verdict_sentence][:2],
        "has_verdict": sum(bool(c.verdict_sentence) for c in checks) / len(checks) if checks else None,
        "facts_up_front": sum(c.facts_up_front for c in checks) / len(checks) if checks else None,
        "title_matches_intent": sum(c.title_matches_intent for c in checks) / len(checks) if checks else None,
        "better_title_template": next((c.better_title_template for c in checks if c.better_title_template), None),
        "questions": [q.model_dump() for q in qs][:8],
    }


def findings(ctx: TemplateContext, checks: list[PageCheck], pages: list[PageFacts]) -> list[Finding]:
    """Claude-backed findings for one page type. `pages` are the checked pages, in order."""
    by_url = {p.url: p for p in pages}
    checked = [by_url[p.url] for p in pages if p.url in by_url][: len(checks)]
    pairs = list(zip(checked, checks, strict=False))
    out: list[Finding | None] = []

    weak = [p for p, c in pairs if c.facts and sum(f.in_text for f in c.facts) / len(c.facts) < 0.7]
    if weak:
        s = summarize(checks)
        out.append(make(ctx, "facts_not_extractable", "ai", "high" if (s["facts_in_text"] or 0) < 0.5 else "medium",
                        f"AI could extract only {round((s['facts_in_text'] or 0) * 100)}% of key facts",
                        "Claude looked for the facts people want from this page type and found these missing or unstated: "
                        + ", ".join(s["missing_facts"][:4]) + ". State them as text (and in JSON-LD), not just in widgets or images.",
                        weak, method="claude"))
    out.append(make(ctx, "no_verdict", "ai", "medium", "No quotable verdict sentence",
                    "Claude found no single sentence an AI answer could lift to sum up the subject. Add one near the top "
                    "that names the entity and states its key facts.",
                    [p for p, c in pairs if not c.verdict_sentence], method="claude"))
    out.append(make(ctx, "facts_buried", "ai", "low", "Key facts not up front",
                    "The most important facts don't appear in the first ~100 words. Put them at the top.",
                    [p for p, c in pairs if not c.facts_up_front], method="claude"))
    bad_title = [p for p, c in pairs if not c.title_matches_intent]
    better = next((c.better_title_template for c in checks if c.better_title_template), None)
    out.append(make(ctx, "title_intent", "ai", "low", "Title doesn't match how people search",
                    "Claude judged the title a poor fit for how people ask about this subject."
                    + (f" Suggested pattern: “{better}”." if better else ""),
                    bad_title, method="claude"))
    return [f for f in out if f]
