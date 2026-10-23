"""Findings and scoring shared by the SEO and AI-readiness checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.checks.page_facts import PageFacts

SEVERITY_PENALTY = {"high": 25, "medium": 10, "low": 4}


@dataclass
class Finding:
    id: str
    area: str  # "seo" | "ai"
    severity: str  # "high" | "medium" | "low"
    title: str
    detail: str
    affected: int  # sample pages that failed
    sampled: int
    pages: int  # estimated pages across the whole template
    examples: list[str] = field(default_factory=list)
    method: str = "rule"  # "rule" | "heuristic" | "claude"

    @property
    def share(self) -> float:
        return self.affected / self.sampled if self.sampled else 0.0


@dataclass
class TemplateContext:
    pattern: str
    estimated_pages: int
    samples: list[PageFacts]
    lastmods: dict[str, str | None]  # sitemap lastmod per URL in this template


def make(ctx: TemplateContext, id: str, area: str, severity: str, title: str, detail: str,
         bad: list[PageFacts], method: str = "rule") -> Finding | None:
    if not bad or not ctx.samples:
        return None
    share = len(bad) / len(ctx.samples)
    return Finding(
        id=id, area=area, severity=severity, title=title, detail=detail,
        affected=len(bad), sampled=len(ctx.samples),
        pages=max(1, round(share * ctx.estimated_pages)),
        examples=[p.url for p in bad[:3]], method=method,
    )


def score(findings: list[Finding], area: str) -> int:
    penalty = sum(SEVERITY_PENALTY[f.severity] * f.share for f in findings if f.area == area)
    return max(0, round(100 - penalty))
