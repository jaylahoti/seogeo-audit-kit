// Turn a live audit into the shapes the module screens render (or return the samples).

import type { Audit } from "@/lib/mock";
import {
  AI_CRAWLERS, AI_ROWS, GENERATED_LLMS_TXT, GENERATED_ROBOTS, LLMS_TXT, RENDER_DIFFS, TECH_CHECKS, TECH_PASSED,
  type AiRow, type RenderDiff, type TechCheck,
} from "@/lib/modules";

const CATEGORY: [RegExp, string][] = [
  [/^(status_error|sitemap_redirect|noindex_in_sitemap|canonical_|hreflang_)/, "Indexability"],
  [/^(title_|desc_)/, "Metadata"],
  [/^(h1_|thin_content|near_duplicate|lang_missing)/, "Content"],
  [/^img_alt/, "Accessibility"],
  [/^(lastmod_)/, "Sitemap"],
  [/^(deep_template)/, "Linking"],
  [/^(slow_response|cwv_)/, "Performance"],
];

function category(id = ""): string {
  return CATEGORY.find(([rx]) => rx.test(id))?.[1] ?? "Other";
}

export function techChecks(audit: Audit): { checks: TechCheck[]; passed: string[] } {
  if (!audit.live) return { checks: TECH_CHECKS, passed: TECH_PASSED };
  const byId = new Map<string, TechCheck>();
  for (const t of audit.templates) {
    for (const f of t.findings.filter((x) => x.area === "seo")) {
      const key = f.id ?? f.title;
      const c = byId.get(key) ?? { check: f.title, category: category(f.id), severity: f.severity, affected: [] };
      c.affected.push({ pattern: t.pattern, pages: f.pages });
      if (f.severity === "high" || (f.severity === "medium" && c.severity === "low")) c.severity = f.severity;
      byId.set(key, c);
    }
  }
  const withSamples = audit.templates.filter((t) => t.passed);
  const passed = withSamples.length
    ? withSamples.map((t) => t.passed ?? []).reduce((acc, p) => acc.filter((x) => p.includes(x)))
    : [];
  return { checks: [...byId.values()], passed };
}

export function aiRows(audit: Audit): AiRow[] {
  if (!audit.live) return AI_ROWS;
  return audit.templates
    .filter((t) => t.samples.some((s) => s.status === 200) && !t.pattern.startsWith("/{static}"))
    .map((t) => {
      const ids = new Set(t.findings.map((f) => f.id));
      const jsonld: AiRow["jsonld"] = ids.has("jsonld_missing") ? "missing"
        : ids.has("jsonld_invalid") || ids.has("jsonld_required") || ids.has("jsonld_placeholders") || ids.has("jsonld_no_entity") ? "invalid"
        : "valid";
      return {
        pattern: t.pattern,
        jsonld,
        fresh: !ids.has("date_modified_missing") && !ids.has("date_modified_stale"),
        verdict: !ids.has("no_verdict"),
        answerFirst: !ids.has("facts_buried"),
        noPlaceholders: !ids.has("visible_placeholders"),
        facts: audit.live!.claudePages[t.pattern]?.facts_in_text ?? null,
        titleIntent: audit.live!.claudePages[t.pattern] ? (audit.live!.claudePages[t.pattern].title_matches_intent ?? 0) >= 0.5 : null,
      };
    });
}

export function aiCrawlers(audit: Audit) {
  return audit.live ? audit.live.robots.ai_crawlers : AI_CRAWLERS;
}

export function llmsStatus(audit: Audit): { found: boolean; issues: string[]; sections?: string[]; links?: number } {
  return audit.live ? audit.live.llmsTxt : LLMS_TXT;
}

export function renderDiffs(audit: Audit): RenderDiff[] {
  if (!audit.live) return RENDER_DIFFS;
  return audit.live.render
    .filter((d) => !d.error)
    .map((d) => ({
      pattern: d.pattern,
      rawWords: d.raw_words,
      renderedWords: d.rendered_words,
      rawLinks: d.raw_links,
      renderedLinks: d.rendered_links,
      jsonldRaw: d.raw_jsonld > 0,
      jsonldRendered: d.rendered_jsonld > 0,
      jsOnly: d.js_only_headings,
    }));
}

export function generatedFixes(audit: Audit) {
  if (!audit.live) return { llms: GENERATED_LLMS_TXT, robots: GENERATED_ROBOTS };
  return { llms: audit.live.fixes.llms_txt, robots: audit.live.fixes.robots_txt };
}
