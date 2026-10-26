// Client for the audit API, plus the adapter from an API result to the report UI's shape.

import type { Audit, Finding, LiveExtras, Stage, Template } from "@/lib/mock";
import { rememberAudit, siteOf } from "@/lib/recent";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";

export type StageEvent = {
  seq: number;
  t: number;
  type: "stage" | "progress" | "done" | "error";
  key?: string;
  label?: string;
  status?: "running" | "done" | "error";
  detail?: string;
  ms?: number;
  cost?: number;
  message?: string;
  [k: string]: unknown;
};

export type ApiAudit = {
  id: string;
  input_url: string;
  status: "queued" | "running" | "done" | "error";
  created_at: number;
  error: string | null;
  events: StageEvent[];
  result: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
};

export async function createAudit(url: string): Promise<{ id: string }> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/audits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  } catch {
    throw new Error("Couldn't reach the audit API. Is it running on " + API_URL + "?");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `The API returned ${res.status}`);
  rememberAudit({ id: body.id, site: siteOf(url), at: Date.now(), status: "running" });
  return body;
}

export async function startCount(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/audits/${encodeURIComponent(id)}/count`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : `The API returned ${res.status}`);
  }
}

async function postLogs(path: string, body?: Blob): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: "POST", body, headers: body ? { "Content-Type": "application/octet-stream" } : undefined });
  } catch {
    throw new Error("Couldn't reach the audit API.");
  }
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw new Error(typeof b.detail === "string" ? b.detail : `The API returned ${res.status}`);
  }
}

/** Upload an access log (plain or .gz). Only the aggregated result is kept on the server. */
export const uploadLogs = (id: string, file: Blob) => postLogs(`/audits/${encodeURIComponent(id)}/logs`, file);
export const sampleLogs = (id: string) => postLogs(`/audits/${encodeURIComponent(id)}/logs/sample`);

export async function getAudit(id: string): Promise<ApiAudit | null> {
  const res = await fetch(`${API_URL}/audits/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`The API returned ${res.status}`);
  return res.json();
}

export function streamEvents(id: string, onEvent: (e: StageEvent) => void): () => void {
  const es = new EventSource(`${API_URL}/audits/${encodeURIComponent(id)}/events`);
  es.onmessage = (m) => {
    const e = JSON.parse(m.data) as StageEvent;
    onEvent(e);
    if (e.type === "done" || e.type === "error") es.close();
  };
  es.onerror = () => es.close();
  return () => es.close();
}

/** Convert an API result into the Audit shape the report screens render. */
export function toAudit(a: ApiAudit): Audit {
  const r = a.result;
  const stagesDone: Stage[] = a.events
    .filter((e) => e.type === "stage" && e.status === "done")
    .map((e) => ({ key: e.key!, label: e.label!, detail: e.detail ?? "", ms: e.ms ?? 0, cost: e.cost ?? 0 }));
  const first = a.events[0]?.t ?? a.created_at;
  const last = a.events[a.events.length - 1]?.t ?? first;
  const cwvBy: Record<string, any> = Object.fromEntries((r.cwv ?? []).map((c: any) => [c.pattern, c])); // eslint-disable-line @typescript-eslint/no-explicit-any

  const answersBy: Record<string, any[]> = {}; // eslint-disable-line @typescript-eslint/no-explicit-any
  for (const a of r.visibility?.answers ?? []) (answersBy[a.page_type] ??= []).push(a);

  const templates: Template[] = (r.templates ?? []).map((t: any, i: number) => { // eslint-disable-line @typescript-eslint/no-explicit-any
    const c = cwvBy[t.pattern];
    const ans = answersBy[t.pattern];
    const pc = r.claude_pages?.[t.pattern];
    return {
      citation: ans?.length
        ? { asked: ans.length, cited: ans.filter((a) => a.status === "cited").length,
            citedInstead: [...new Set(ans.flatMap((a) => a.cited_instead as string[]))].slice(0, 5) as string[] }
        : undefined,
      evidence: r.claude_evidence?.[t.pattern],
      questions: pc?.questions?.map((q: { question: string }) => q.question).slice(0, 4),
      id: `t${i}`,
      pattern: t.variant ? `${t.pattern} · layout ${t.variant}` : t.pattern,
      pages: t.estimated_pages,
      seo: t.seo_score ?? 0,
      ai: t.ai_score ?? 0,
      examples: t.examples,
      passed: t.passed,
      cwv: c && c.source !== "error" ? { lcp: c.lcp_ms != null ? c.lcp_ms / 1000 : null, cls: c.cls, inp: c.inp_ms, source: c.source } : undefined,
      findings: (t.findings ?? []).map((f: any): Finding => ({ // eslint-disable-line @typescript-eslint/no-explicit-any
        id: f.id, area: f.area, severity: f.severity, title: f.title, detail: f.detail, pages: f.pages,
        affected: f.affected, sampled: f.sampled, examples: f.examples, method: f.method, fix: f.fix,
      })),
      samples: (t.samples ?? []).map((s: any) => ({ url: s.url, status: s.status, words: s.words, schema: s.schema, title: s.title, ms: s.ms })), // eslint-disable-line @typescript-eslint/no-explicit-any
    };
  });

  const live: LiveExtras = {
    crawlerLogs: r.crawler_logs ?? null,
    claudeEnabled: (r.claude?.calls?.length ?? 0) > 0,
    claudeSpent: r.claude?.spent ?? 0,
    claudeBudget: r.claude?.budget ?? 0,
    claudeCalls: r.claude?.calls ?? [],
    claudePages: r.claude_pages ?? {},
    visibility: r.visibility ?? null,
    judge: r.judge ?? null,
    gaps: r.question_gaps ?? [],
    monitoring: r.monitoring ?? null,
    sitemapSource: r.sitemap?.source === "links" ? "links" : "sitemap",
    pageCount: {
      leavesTotal: r.sitemap?.leaves_total ?? 0,
      leavesRead: r.sitemap?.leaves_read ?? 0,
      urlsSampled: r.sitemap?.urls_sampled ?? 0,
      families: r.sitemap?.families ?? [],
      estimatedTotal: r.sitemap?.urls_estimated ?? 0,
    },
    exactCount: r.exact_count ?? null,
    robots: r.robots ?? { found: false, sitemaps: [], ai_crawlers: [], blocked_retrieval_bots: [] },
    llmsTxt: r.llms_txt ?? { found: false, title: null, sections: [], links: 0, issues: [] },
    render: r.render ?? [],
    cwvErrors: (r.cwv ?? []).filter((c: any) => c.error).map((c: any) => c.error), // eslint-disable-line @typescript-eslint/no-explicit-any
    fixes: r.fixes ?? { llms_txt: "", robots_txt: "" },
    links: r.links ?? { depth: {}, bfs_pages: 0, probed: 0, broken: [], redirecting: [] },
    siteFindings: r.site_findings ?? [],
    ml: { pages: r.ml?.pages ?? 0, layouts: r.ml?.layouts ?? 0, noise: r.ml?.noise ?? 0, points: r.ml?.points ?? [] },
    crawl: r.crawl ?? { requested: 0, ok: 0, non_200: 0, errors: 0, blocked_by_robots: 0, avg_ms: 0 },
  };

  // After "Count every page", swap estimates for exact counts (per template and in findings).
  const exact = live.exactCount?.status === "done" ? live.exactCount : null;
  if (exact) {
    const base = (p: string) => p.replace(/ · layout \d+$/, "");
    const estByBase: Record<string, number> = {};
    for (const t of templates) estByBase[base(t.pattern)] = (estByBase[base(t.pattern)] ?? 0) + t.pages;
    for (const t of templates) {
      const b = base(t.pattern);
      const counted = b === "/{static}" ? exact.unmatched : exact.templates[b];
      if (counted == null || !estByBase[b]) continue;
      const exactPages = Math.round(counted * (t.pages / estByBase[b])); // split layouts by their share
      const factor = t.pages ? exactPages / t.pages : 1;
      t.pages = exactPages;
      t.findings = t.findings.map((f) => ({ ...f, pages: Math.max(1, Math.round(f.pages * factor)) }));
    }
  }

  let host = a.input_url;
  try { host = new URL(a.input_url).hostname; } catch { /* keep the raw input */ }

  return {
    id: a.id,
    site: host,
    sitemap: r.sitemap?.start?.[0] ?? a.input_url,
    ranAt: new Date(a.created_at * 1000).toISOString(),
    urls: exact ? exact.urls : r.sitemap?.urls_estimated ?? 0,
    scores: r.scores ?? { seo: 0, ai: 0 },
    cost: r.claude?.spent ?? stagesDone.reduce((s, x) => s + x.cost, 0),
    naiveCost: r.naive_cost_usd ?? 0,
    durationSec: Math.round(last - first),
    templates,
    stages: stagesDone,
    inputUrl: a.input_url,
    geo: r.geo,
    live,
  };
}
