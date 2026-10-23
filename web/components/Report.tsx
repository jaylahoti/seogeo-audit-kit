"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { Audit, Finding, Template } from "@/lib/mock";
import { fmt, SAMPLE_AUDIT } from "@/lib/mock";
import { MODULES } from "@/lib/modules";
import { Bar, ScoreRing, scoreColor } from "@/components/Score";
import { TemplateDetail } from "@/components/TemplateDetail";
import { MlLab } from "@/components/MlLab";
import { GeoCard } from "@/components/GeoCard";
import { AccessBadge, ModuleHead } from "@/components/ui";
import { CommandPalette } from "@/components/CommandPalette";
import { RerunButton } from "@/components/NewAudit";
import { useReportRefresh } from "@/components/RefreshContext";
import { startCount } from "@/lib/api";
import { AiReadiness, CoreWebVitals, Fixes, TechnicalSeo, WhatAiSees } from "@/components/modules/Audit";
import { AiTraffic, Bing } from "@/components/modules/Connect";
import { AiCrawlers, AiVisibility, CiMcp, Monitoring, QuestionGaps } from "@/components/modules/Track";

const SEV_WEIGHT = { high: 3, medium: 2, low: 1 } as const;
const GROUPS = ["Audit", "Connect", "Track", "Lab"] as const;

export function Report({ audit }: { audit: Audit }) {
  const params = useSearchParams();
  const router = useRouter();
  const current = MODULES.find((m) => m.id === params.get("m"))?.id ?? "overview";
  // push (not replace) so the phone's back gesture returns to the hub.
  const go = (id: string) => { router.push(`?m=${id}`, { scroll: false }); window.scrollTo({ top: 0 }); };
  const idx = MODULES.findIndex((m) => m.id === current);
  const prev = idx > 0 ? MODULES[idx - 1] : null;
  const next = idx < MODULES.length - 1 ? MODULES[idx + 1] : null;
  const [copied, setCopied] = useState(false);

  const topFixes = useMemo(() => {
    const all: (Finding & { template: string })[] = audit.templates.flatMap((t) =>
      t.findings.map((f) => ({ ...f, template: t.pattern })),
    );
    return all.sort((a, b) => SEV_WEIGHT[b.severity] * b.pages - SEV_WEIGHT[a.severity] * a.pages).slice(0, 5);
  }, [audit]);

  return (
    <div className="mx-auto max-w-[1280px] px-4 py-6">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--line)] pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs text-[var(--muted)]">
            {audit.live ? <span className="pill bg-[var(--good-soft)] text-[var(--good)]">Live audit</span> : <span className="pill sev-low">Sample report</span>}
            <span>Ran {new Date(audit.ranAt).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" })} UTC</span>
          </div>
          <h1 className="mt-2 text-2xl font-semibold">{audit.site}</h1>
          <p className="mono mt-0.5 text-xs text-[var(--muted)]">{audit.sitemap} · {audit.live && audit.live.sitemapSource === "sitemap" && audit.live.exactCount?.status !== "done" && audit.live.pageCount.leavesRead < audit.live.pageCount.leavesTotal ? `~${fmt(audit.urls)} pages (estimated)` : `${fmt(audit.urls)} pages`} · {audit.templates.length} page types</p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn"
            onClick={() => { navigator.clipboard?.writeText(location.href); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
          >
            {copied ? "Link copied" : "Share"}
          </button>
          <button className="btn" onClick={() => window.print()}>Export PDF</button>
          {audit.live && audit.inputUrl ? <RerunButton url={audit.inputUrl} /> : <a className="btn btn-primary" href="/#audit">Audit your own site</a>}
        </div>
      </div>

      {/* Mobile: the Overview is the hub; module pages link back to it. */}
      {current !== "overview" && (
        <button onClick={() => go("overview")} className="mt-4 inline-flex items-center gap-1.5 text-sm text-[var(--muted)] hover:text-[var(--text)] lg:hidden">
          <span aria-hidden>←</span> All modules
        </button>
      )}

      <div className="mt-5 grid gap-8 lg:grid-cols-[220px_minmax(0,1fr)]">
        <nav aria-label="Report modules" className="hidden lg:block">
          <div className="sticky top-20 space-y-5">
            <CommandPalette go={go} />
            {GROUPS.map((g) => (
              <div key={g}>
                <div className="mb-1.5 px-2 text-[11px] font-medium uppercase tracking-wide text-[var(--faint)]">{g}</div>
                <ul className="space-y-0.5">
                  {MODULES.filter((m) => m.group === g).map((m) => (
                    <li key={m.id}>
                      <button
                        onClick={() => go(m.id)}
                        aria-current={current === m.id ? "page" : undefined}
                        className={`flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm ${current === m.id ? "bg-[var(--sunken)] font-medium" : "text-[var(--muted)] hover:bg-[var(--sunken)] hover:text-[var(--text)]"}`}
                      >
                        <span className="truncate">{m.label}</span>
                        {m.access !== "free" && <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${m.access === "claude" ? "bg-[var(--accent)]" : m.access === "connect" ? "bg-[var(--good)]" : "bg-[var(--warn)]"}`} />}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
            <div className="space-y-1 border-t border-[var(--line)] px-2 pt-3 text-[11px] text-[var(--faint)]">
              <div className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-[var(--accent)]" /> Uses Claude</div>
              <div className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-[var(--good)]" /> Connect an account</div>
            </div>
          </div>
        </nav>

        <main className="min-w-0">
          {current === "overview" && <Overview audit={audit} topFixes={topFixes} go={go} />}
          {current === "technical" && <TechnicalSeo audit={audit} />}
          {current === "cwv" && <CoreWebVitals audit={audit} />}
          {current === "ai" && <AiReadiness audit={audit} />}
          {current === "whatai" && <WhatAiSees audit={audit} />}
          {current === "fixes" && <Fixes audit={audit} />}
          {audit.live && SAMPLE_ONLY.has(current) && <SampleBanner id={current} />}
          {current === "gsc" && <SearchConsole templates={audit.live ? SAMPLE_AUDIT.templates : audit.templates} />}
          {current === "bing" && <Bing />}
          {current === "traffic" && <AiTraffic />}
          {current === "visibility" && <AiVisibility />}
          {current === "crawlers" && <AiCrawlers />}
          {current === "monitoring" && <Monitoring />}
          {current === "gaps" && <QuestionGaps />}
          {current === "ci" && <CiMcp />}
          {current === "ml" && <><ModuleHead title="ML Lab" desc="How the template detection and the AI judge are measured." access="free" /><MlLab audit={audit} /></>}
          {current === "trace" && <><ModuleHead title="Trace and cost" desc="Every pipeline stage, how long it took and what it cost." access="free" /><Trace audit={audit} /></>}

          {current !== "overview" && (
            <div className="mt-10 grid grid-cols-2 gap-3 border-t border-[var(--line)] pt-5 text-sm">
              {prev ? (
                <button onClick={() => go(prev.id)} className="card p-3 text-left hover:border-[var(--line-strong)]">
                  <div className="text-xs text-[var(--faint)]">← Previous</div><div className="truncate font-medium">{prev.label}</div>
                </button>
              ) : <span />}
              {next ? (
                <button onClick={() => go(next.id)} className="card p-3 text-right hover:border-[var(--line-strong)]">
                  <div className="text-xs text-[var(--faint)]">Next →</div><div className="truncate font-medium">{next.label}</div>
                </button>
              ) : <span />}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

// Modules that need connected accounts, logs, schedules or Claude: real audits show samples for now.
const SAMPLE_ONLY = new Set(["gsc", "bing", "traffic", "visibility", "crawlers", "monitoring", "gaps", "ci"]);
const SAMPLE_REASON: Record<string, string> = {
  gsc: "Connect Google Search Console (coming with account connections).",
  bing: "Connect Bing Webmaster with a free API key (coming with account connections).",
  traffic: "Connect GA4 or PostHog (coming with account connections).",
  visibility: "Citation tracking runs on Claude with web search (coming with the Claude checks).",
  crawlers: "Upload or stream your access logs (coming soon).",
  monitoring: "Scheduled re-audits need saved audits (coming with the database).",
  gaps: "Question gaps are generated by Claude (coming with the Claude checks).",
  ci: "The GitHub Action and MCP server are being packaged.",
};

function SampleBanner({ id }: { id: string }) {
  return (
    <div className="mb-5 rounded-xl border border-dashed border-[var(--line-strong)] px-4 py-3 text-sm">
      <span className="font-medium">Sample data — not from this audit.</span>{" "}
      <span className="text-[var(--muted)]">{SAMPLE_REASON[id]}</span>
    </div>
  );
}

function countMethod(audit: Audit): string {
  const L = audit.live!;
  const pc = L.pageCount;
  if (L.sitemapSource === "links") return `Found by following links · no sitemap`;
  if (L.exactCount?.status === "done") return `Exact count from all ${fmt(L.exactCount.files_total)} sitemap files`;
  if (pc.leavesRead < pc.leavesTotal) return `Smart sampling · estimated from ${pc.leavesRead} of ${pc.leavesTotal} sitemap files`;
  return `Counted from all ${pc.leavesTotal} sitemap file${pc.leavesTotal === 1 ? "" : "s"}`;
}

const prettyFamily = (f: string) => f.replace(/^\//, "").replace(/#/g, "{n}");

function PageCount({ audit }: { audit: Audit }) {
  const L = audit.live!;
  const pc = L.pageCount;
  const ex = L.exactCount;
  const refresh = useReportRefresh();
  const [starting, setStarting] = useState(false);
  const [err, setErr] = useState("");

  // While counting, poll the API and refresh the report when it's done.
  useEffect(() => {
    if (ex?.status !== "running") return;
    const timer = setInterval(() => { refresh(); }, 1500);
    return () => clearInterval(timer);
  }, [ex?.status, refresh]);

  async function count() {
    setStarting(true); setErr("");
    try { await startCount(audit.id); await refresh(); } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't start counting"); }
    setStarting(false);
  }

  if (L.sitemapSource === "links") {
    return (
      <details className="card group p-4">
        <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium">
          How pages were counted <span className="text-[var(--faint)] transition group-open:rotate-45">+</span>
        </summary>
        <p className="mt-2 text-sm text-[var(--muted)]">
          This site has no sitemap (none listed in robots.txt or at the usual paths), so pages were found by following links from the home page.
          {" "}{fmt(audit.urls)} pages were found; the site may have more that aren't linked within a few clicks.
        </p>
      </details>
    );
  }

  const sampled = pc.leavesRead < pc.leavesTotal;
  const done = ex?.status === "done";
  const diff = done && pc.estimatedTotal ? (pc.estimatedTotal - ex!.urls) / ex!.urls : null;
  const summary = done
    ? `${fmt(ex!.urls)} pages, counted from all ${fmt(ex!.files_total)} sitemap files`
    : sampled
      ? `~${fmt(pc.estimatedTotal)} pages, estimated from ${pc.leavesRead} of ${pc.leavesTotal} sitemap files`
      : `${fmt(pc.estimatedTotal)} pages from all ${pc.leavesTotal} sitemap files`;
  const checked = audit.templates.reduce((n, t) => n + t.samples.filter((x) => x.status === 200).length, 0);
  const funnel: [string, string][] = [
    [`${sampled && !done ? "~" : ""}${fmt(done ? ex!.urls : pc.estimatedTotal)}`, "pages on the site"],
    [fmt(pc.urlsSampled), `page addresses read from ${pc.leavesRead} sitemap files to find the page types`],
    [String(audit.templates.length), "page types found"],
    [fmt(L.crawl.ok), "pages downloaded to confirm each page type's layout"],
    [fmt(checked), "pages checked (about 5 per page type)"],
  ];

  return (
    <details className="card group p-4" open={ex?.status === "running" || undefined}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm">
        <span><span className="font-medium">How pages were counted</span><span className="ml-2 text-[var(--muted)]">{summary}</span></span>
        <span className="text-[var(--faint)] transition group-open:rotate-45">+</span>
      </summary>

      <ol className="mt-4 grid gap-px overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--line)] sm:grid-cols-5">
        {funnel.map(([n, label], i) => (
          <li key={label} className="bg-[var(--panel)] p-3">
            <div className="mono text-lg font-semibold">{n}</div>
            <div className="mt-0.5 text-xs text-[var(--muted)]">{label}</div>
            {i < funnel.length - 1 && <span className="sr-only">, then</span>}
          </li>
        ))}
      </ol>

      {sampled && !done && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-[var(--sunken)] px-3 py-2.5 text-sm">
          {ex?.status === "running" ? (
            <div className="min-w-0 flex-1">
              <div>Counting every page… {fmt(ex.files_done)} of {fmt(Math.max(ex.files_total, pc.leavesTotal))} files · {fmt(ex.urls)} URLs so far</div>
              <div className="mt-2 h-1 overflow-hidden rounded-full bg-[var(--line)]">
                <div className="h-full rounded-full bg-[var(--accent)] transition-all" style={{ width: `${Math.min(100, (ex.files_done / Math.max(1, ex.files_total, pc.leavesTotal)) * 100)}%` }} />
              </div>
            </div>
          ) : (
            <>
              <span className="text-[var(--muted)]">
                {ex?.status === "error" ? <span className="text-[var(--bad)]">{ex.error}</span> : "Need the exact number? Read every sitemap file (counts only — the findings don't change)."}
              </span>
              <button className="btn" onClick={count} disabled={starting}>{starting ? "Starting…" : "Count every page"}</button>
            </>
          )}
          {err && <span className="w-full text-xs text-[var(--bad)]">{err}</span>}
        </div>
      )}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[420px] text-sm">
          <thead className="whitespace-nowrap text-left text-xs text-[var(--faint)]">
            <tr>
              <th className="py-2 font-normal">Sitemap family</th>
              <th className="font-normal">Files read</th>
              <th className="hidden text-right font-normal sm:table-cell">Sampled</th>
              <th className="text-right font-normal">{done ? "Estimated" : "Estimated pages"}</th>
              {done && <th className="text-right font-normal">Exact</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--line)]">
            {pc.families.map((f) => {
              const exactFam = ex?.families[f.family];
              return (
                <tr key={f.family}>
                  <td className="mono max-w-[160px] truncate py-2 pr-4 text-xs sm:max-w-[260px]" title={prettyFamily(f.family)}>{prettyFamily(f.family)}</td>
                  <td className="mono whitespace-nowrap text-xs">
                    {f.files_read} of {f.files_total}
                    {!done && f.files_read < f.files_total && <span className="block text-[10px] text-[var(--faint)]">{f.files_total - f.files_read} estimated</span>}
                  </td>
                  <td className="mono hidden text-right text-xs sm:table-cell">{fmt(f.urls_sampled)}</td>
                  <td className={`mono text-right text-xs ${done ? "text-[var(--muted)]" : "font-medium"}`}>{f.files_read ? `${f.files_read < f.files_total ? "~" : ""}${fmt(f.estimated)}` : "not read"}</td>
                  {done && <td className="mono text-right text-xs font-medium">{exactFam ? fmt(exactFam.urls) : "—"}</td>}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-xs text-[var(--faint)]">
        {done
          ? `Exact count from every sitemap file. The smart-sampling estimate was ${fmt(pc.estimatedTotal)} — ${diff != null ? `${Math.abs(diff * 100).toFixed(1)}% ${diff >= 0 ? "high" : "low"}` : "close"}. Template page counts and “fix covers” numbers now use the exact count.`
          : sampled
            ? "Smart sampling: pages built from one template share its problems, so the audit reads a fair sample of sitemap files across every family and checks about 5 representative pages per template. Each family's count is scaled up — URLs in the files read × (files in the family ÷ files read) — assuming unread files are about the size of the ones read, which holds for numbered files that fill to the same limit."
            : "Every sitemap file was read, so these are exact counts. Only a sample of URLs is used for the checks, since a template's problems show up on a few pages."}
      </p>
    </details>
  );
}

function liveSummary(audit: Audit, id: string): string | null {
  const L = audit.live;
  if (!L) return null;
  const all = audit.templates.flatMap((t) => t.findings);
  switch (id) {
    case "technical": {
      const seo = all.filter((f) => f.area === "seo");
      return `${new Set(seo.map((f) => f.id)).size} issues across ${audit.templates.filter((t) => t.findings.some((f) => f.area === "seo")).length} page types`;
    }
    case "cwv": {
      const n = audit.templates.filter((t) => t.cwv).length;
      return n ? `${n} page types measured` : "Needs a free PSI_API_KEY";
    }
    case "ai":
      return `AI readiness ${audit.scores.ai} · ${L.llmsTxt.found ? "llms.txt found" : "no llms.txt"}`;
    case "whatai": {
      const worst = [...L.render].sort((a, b) => b.js_text_share - a.js_text_share)[0];
      return worst && worst.js_text_share >= 0.2 ? `${Math.round(worst.js_text_share * 100)}% of ${worst.pattern} needs JavaScript` : "Content is server-rendered";
    }
    case "fixes":
      return "llms.txt and robots.txt generated";
    case "ml":
      return `${L.ml.layouts} layouts from ${L.ml.pages} pages`;
    case "trace":
      return `${audit.stages.length} stages · ${audit.durationSec}s · $${audit.cost.toFixed(2)}`;
    default:
      return "Sample data for now";
  }
}

const MODULE_SUMMARY: Record<string, string> = {
  technical: "10 issues · 4 page types",
  cwv: "2 page types fail LCP",
  ai: "AI readiness 48 · no llms.txt",
  whatai: "78% of building text needs JavaScript",
  fixes: "9 fixes ready to paste",
  gsc: "41% of submitted pages indexed",
  bing: "21% indexed in Bing",
  traffic: "968 AI visits last week · +13%",
  visibility: "Cited in 8 of 24 answers",
  crawlers: "PerplexityBot blocked",
  monitoring: "2 regressions since Oct 12",
  gaps: "2 question families have no page",
  ci: "GitHub Action + MCP server",
  ml: "Clustering ARI 0.91 · judge κ 0.78",
  trace: "$0.11 per audit · 94s",
};

function Overview({ audit, topFixes, go }: { audit: Audit; topFixes: (Finding & { template: string })[]; go: (id: string) => void }) {
  const [open, setOpen] = useState<string | null>(audit.templates[0]?.id ?? null);
  const sorted = [...audit.templates].sort((a, b) => impact(b) - impact(a));
  const totals = audit.templates.reduce(
    (s, t) => ({ submitted: s.submitted + (t.submitted ?? 0), indexed: s.indexed + (t.indexed ?? 0) }),
    { submitted: 0, indexed: 0 },
  );
  const siteFindings = audit.live?.siteFindings ?? [];

  return (
    <div className="space-y-8">
      {audit.geo && <GeoCard geo={audit.geo} />}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <div className="card p-4"><ScoreRing value={audit.scores.seo} label="SEO health" size={72} /></div>
        <div className="card p-4"><ScoreRing value={audit.scores.ai} label="AI readiness" size={72} /></div>
        {audit.live ? (
          <div className="card p-4">
            <div className="text-xs text-[var(--muted)]">{audit.live.sitemapSource === "links" ? "Pages found (no sitemap)" : "Pages in the sitemap"}</div>
            <div className="mt-1 text-2xl font-semibold">{audit.live.sitemapSource === "links" || audit.live.exactCount?.status === "done" || audit.live.pageCount.leavesRead >= audit.live.pageCount.leavesTotal ? "" : "~"}{fmt(audit.urls)}</div>
            <div className="text-xs text-[var(--faint)]">{countMethod(audit)}</div>
          </div>
        ) : (
          <div className="card p-4">
            <div className="text-xs text-[var(--muted)]">Indexed (Google)</div>
            <div className="mt-1 text-2xl font-semibold">{Math.round((totals.indexed / Math.max(1, totals.submitted)) * 100)}%</div>
            <div className="text-xs text-[var(--faint)]">{fmt(totals.indexed)} of {fmt(totals.submitted)} submitted</div>
          </div>
        )}
        <div className="card p-4">
          <div className="text-xs text-[var(--muted)]">Audit cost</div>
          <div className="mono mt-1 text-2xl font-semibold">${audit.cost.toFixed(2)}</div>
          <div className="text-xs text-[var(--faint)]">
            {audit.naiveCost > 0
              ? `vs $${audit.naiveCost.toFixed(2)} naive · ${((1 - audit.cost / audit.naiveCost) * 100).toFixed(1)}% saved · ${audit.durationSec}s`
              : `No Claude calls yet · ${Math.floor(audit.durationSec / 60)}m ${audit.durationSec % 60}s`}
          </div>
        </div>
      </div>

      {audit.live && <PageCount audit={audit} />}

      {siteFindings.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold">Site-wide</h2>
          <ul className="card divide-y divide-[var(--line)]">
            {siteFindings.map((f) => (
              <li key={f.id} className="flex items-start gap-3 px-4 py-3 text-sm">
                <span className={`pill sev-${f.severity} mt-0.5 w-16 justify-center capitalize`}>{f.severity}</span>
                <div className="min-w-0"><div className="font-medium">{f.title}</div><div className="text-xs text-[var(--muted)]">{f.detail}</div></div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-sm font-semibold">All modules</h2>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {MODULES.filter((m) => m.id !== "overview").map((m) => (
            <button key={m.id} onClick={() => go(m.id)} className="card flex items-start justify-between gap-3 p-3 text-left transition hover:border-[var(--line-strong)]">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-sm font-medium">{m.label}<span className="text-[var(--faint)] lg:hidden" aria-hidden>›</span></div>
                <div className="mt-0.5 truncate text-xs text-[var(--muted)]">{liveSummary(audit, m.id) ?? MODULE_SUMMARY[m.id]}</div>
              </div>
              <AccessBadge access={m.access} />
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold">Top fixes across the site</h2>
        <ol className="card divide-y divide-[var(--line)]">
          {topFixes.map((f, i) => (
            <li key={i} className="flex items-center gap-3 px-4 py-3 text-sm">
              <span className="mono w-4 text-xs text-[var(--faint)]">{i + 1}</span>
              <span className={`pill sev-${f.severity} w-16 justify-center capitalize`}>{f.severity}</span>
              <span className="min-w-0 flex-1 truncate">{f.title}</span>
              <span className="mono hidden truncate text-xs text-[var(--muted)] md:block">{f.template}</span>
              <span className="pill sev-low">{f.area === "ai" ? "AI" : "SEO"}</span>
              <span className="mono w-24 text-right text-xs">{fmt(f.pages)} pages</span>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="text-sm font-semibold">Page types, by impact</h2>
        <p className="mb-3 mt-0.5 text-xs text-[var(--muted)]">A page type (template) is one layout used for many pages — like every building page. Fix it once and every page built from it is fixed.</p>
        <div className="card overflow-hidden">
          <div className="hidden grid-cols-[minmax(0,2fr)_90px_110px_110px_90px_24px] gap-4 border-b border-[var(--line)] px-4 py-2 text-xs text-[var(--faint)] md:grid">
            <span>Page type</span><span className="text-right">Pages</span><span>SEO</span><span>AI readiness</span><span className="text-right">Issues</span><span />
          </div>
          {sorted.map((t) => (
            <div key={t.id} className="border-b border-[var(--line)] last:border-0">
              <button
                onClick={() => setOpen(open === t.id ? null : t.id)}
                aria-expanded={open === t.id}
                className={`grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-4 py-3 text-left text-sm hover:bg-[var(--sunken)] md:grid-cols-[minmax(0,2fr)_90px_110px_110px_90px_24px] ${open === t.id ? "bg-[var(--sunken)]" : ""}`}
              >
                <span className="mono truncate">{t.pattern}</span>
                <span className="mono text-right text-xs text-[var(--muted)] md:text-sm md:text-[var(--text)]">{fmt(t.pages)}</span>
                <ScoreCell v={t.seo} />
                <ScoreCell v={t.ai} />
                <span className="hidden text-right md:block"><IssueSummary t={t} /></span>
                <span className="hidden text-[var(--faint)] md:block">{open === t.id ? "▾" : "▸"}</span>
              </button>
              {open === t.id && <TemplateDetail t={t} />}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function impact(t: Template) {
  return t.findings.reduce((s, f) => s + SEV_WEIGHT[f.severity] * f.pages, 0);
}

function ScoreCell({ v }: { v: number }) {
  return (
    <span className="hidden items-center gap-2 md:flex">
      <span className="mono w-6 text-sm tabular-nums" style={{ color: scoreColor(v) }}>{v}</span>
      <Bar value={v} />
    </span>
  );
}

function IssueSummary({ t }: { t: Template }) {
  const high = t.findings.filter((f) => f.severity === "high").length;
  const med = t.findings.filter((f) => f.severity === "medium").length;
  if (high) return <span className="pill sev-high">{high} high</span>;
  if (med) return <span className="pill sev-medium">{med} med</span>;
  return <span className="pill sev-low">{t.findings.length} low</span>;
}

function SearchConsole({ templates }: { templates: Template[] }) {
  return (
    <div className="space-y-6">
      <ModuleHead num={2} access="connect" title="Search Console" desc="Indexation, clicks and 'why not indexed' reasons per template, from your Google Search Console property. Read-only access." />
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[var(--line)] bg-[var(--sunken)] px-4 py-3 text-sm">
        <span>Connected to <span className="mono">sc-domain:nestlist.example</span> · last 28 days</span>
        <span className="text-xs text-[var(--muted)]">Read-only access · disconnect anytime</span>
      </div>
      <div className="card overflow-hidden">
        <div className="hidden grid-cols-[minmax(0,1.6fr)_minmax(0,2fr)_90px_100px] gap-4 border-b border-[var(--line)] px-4 py-2 text-xs text-[var(--faint)] md:grid">
          <span>Page type</span><span>Indexed / submitted</span><span className="text-right">Clicks</span><span className="text-right">Impressions</span>
        </div>
        {templates.map((t) => {
          const indexed = t.indexed ?? 0, submitted = t.submitted ?? 0;
          const pct = Math.round((indexed / Math.max(1, submitted)) * 100);
          return (
            <div key={t.id} className="grid grid-cols-1 gap-2 border-b border-[var(--line)] px-4 py-3 text-sm last:border-0 md:grid-cols-[minmax(0,1.6fr)_minmax(0,2fr)_90px_100px] md:items-center md:gap-4">
              <span className="mono truncate">{t.pattern}</span>
              <span className="flex items-center gap-3">
                <Bar value={pct} />
                <span className="mono w-36 shrink-0 text-xs text-[var(--muted)]">{fmt(indexed)} / {fmt(submitted)} · <b style={{ color: scoreColor(pct) }}>{pct}%</b></span>
              </span>
              <span className="mono text-xs md:text-right md:text-sm">{fmt(t.clicks ?? 0)}</span>
              <span className="mono text-xs text-[var(--muted)] md:text-right md:text-sm">{fmt(t.impressions ?? 0)}</span>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-[var(--faint)]">
        Indexation comes from Search Console sitemaps and a sample of URL Inspection results per template (API quota: 2,000 inspections a day).
      </p>
    </div>
  );
}

function Trace({ audit }: { audit: Audit }) {
  const total = audit.stages.reduce((s, x) => s + x.ms, 0);
  let offset = 0;
  return (
    <div className="space-y-4">
      <div className="card divide-y divide-[var(--line)]">
        {audit.stages.map((s) => {
          const left = (offset / total) * 100;
          const width = Math.max(0.8, (s.ms / total) * 100);
          offset += s.ms;
          return (
            <div key={s.key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-3 text-sm md:grid-cols-[180px_minmax(0,1fr)_120px_70px_70px] md:items-center">
              <div>
                <div>{s.label}</div>
                <div className="truncate text-xs text-[var(--muted)]">{s.detail}</div>
              </div>
              <div className="relative hidden h-2 rounded-full bg-[var(--sunken)] md:block">
                <div className="absolute h-2 rounded-full" style={{ left: `${left}%`, width: `${width}%`, background: s.model ? "var(--accent)" : "var(--line-strong)" }} />
              </div>
              <span className="hidden text-xs text-[var(--muted)] md:block">{s.model ? `${s.model} · ${fmt(s.tokens ?? 0)} tok` : "code / ML"}</span>
              <span className="mono text-right text-xs">{(s.ms / 1000).toFixed(1)}s</span>
              <span className="mono hidden text-right text-xs md:block">${s.cost.toFixed(3)}</span>
            </div>
          );
        })}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="sunken p-4 text-sm"><div className="text-xs text-[var(--muted)]">Why it's cheap</div><p className="mt-1">Rules and ML run first for free. Claude only reads 30 sample pages, not 4,812.</p></div>
        <div className="sunken p-4 text-sm"><div className="text-xs text-[var(--muted)]">Model routing</div><p className="mt-1">Haiku for page-level extraction, Sonnet once for judging and writing fixes.</p></div>
        <div className="sunken p-4 text-sm"><div className="text-xs text-[var(--muted)]">Guardrails</div><p className="mt-1">Generated JSON-LD is validated against schema.org before it's shown.</p></div>
      </div>
    </div>
  );
}
