"use client";

import { useState } from "react";
import type { Template } from "@/lib/mock";
import { fmt } from "@/lib/mock";
import {
  AI_CRAWLERS, AI_ROWS, GENERATED_LLMS_TXT, GENERATED_ROBOTS, LLMS_TXT, RENDER_DIFFS,
  TECH_CHECKS, TECH_PASSED, TITLE_EXAMPLE, VERDICT_EXAMPLE,
} from "@/lib/modules";
import { Bar, scoreColor } from "@/components/Score";
import { Check, CodeBlock, ModuleHead, Notice, Stat, Table, td } from "@/components/ui";

const SEV_ORDER = { high: 0, medium: 1, low: 2 } as const;

export function TechnicalSeo() {
  const [cat, setCat] = useState("All");
  const cats = ["All", ...Array.from(new Set(TECH_CHECKS.map((c) => c.category)))];
  const rows = TECH_CHECKS.filter((c) => cat === "All" || c.category === cat).sort((a, b) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);
  const pages = TECH_CHECKS.reduce((s, c) => s + c.affected.reduce((x, a) => x + a.pages, 0), 0);
  return (
    <div>
      <ModuleHead num={1} access="free" title="Technical SEO" desc="Crawl checks run on sample pages from every template. Each issue shows which templates it affects and how many pages one fix covers." />
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Issues" value={String(TECH_CHECKS.length)} note={`${TECH_CHECKS.filter((c) => c.severity === "high").length} high severity`} />
        <Stat label="Page-level occurrences" value={fmt(pages)} note="fixed by 10 template changes" />
        <Stat label="Checks passed" value={String(TECH_PASSED.length)} note="of 16 run" />
      </div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {cats.map((c) => (
          <button key={c} onClick={() => setCat(c)} className={`rounded-full border px-3 py-1 text-xs ${cat === c ? "border-[var(--text)] bg-[var(--text)] text-[var(--bg)]" : "border-[var(--line)] text-[var(--muted)] hover:text-[var(--text)]"}`}>{c}</button>
        ))}
      </div>
      <Table head={["Severity", "Check", "Category", "Templates affected", "Pages"]}>
        {rows.map((c) => (
          <tr key={c.check}>
            <td className={td}><span className={`pill sev-${c.severity} capitalize`}>{c.severity}</span></td>
            <td className={td}>{c.check}</td>
            <td className={`${td} text-xs text-[var(--muted)]`}>{c.category}</td>
            <td className={td}>{c.affected.map((a) => <div key={a.pattern} className="mono text-xs">{a.pattern}</div>)}</td>
            <td className={`${td} mono text-right`}>{fmt(c.affected.reduce((s, a) => s + a.pages, 0))}</td>
          </tr>
        ))}
      </Table>
      <div className="mt-4 flex flex-wrap gap-2 text-xs">
        {TECH_PASSED.map((p) => <span key={p} className="rounded-full bg-[var(--good-soft)] px-2.5 py-1 text-[var(--good)]">✓ {p}</span>)}
      </div>
    </div>
  );
}

export function CoreWebVitals({ templates }: { templates: Template[] }) {
  const vitals = [
    { key: "lcp" as const, label: "LCP", unit: "s", good: 2.5, poor: 4, max: 5 },
    { key: "cls" as const, label: "CLS", unit: "", good: 0.1, poor: 0.25, max: 0.3 },
    { key: "inp" as const, label: "INP", unit: "ms", good: 200, poor: 500, max: 600 },
  ];
  const color = (v: number, good: number, poor: number) => (v <= good ? "var(--good)" : v <= poor ? "var(--warn)" : "var(--bad)");
  return (
    <div>
      <ModuleHead num={3} access="free" title="Core Web Vitals" desc="Mobile p75 per template. Field data from the Chrome UX Report when Google has enough traffic; otherwise lab data from PageSpeed Insights on sample pages." />
      <Table head={["Template", "Pages", ...vitals.map((v) => `${v.label} (good ≤ ${v.good}${v.unit})`), "Source"]} minWidth={760}>
        {templates.map((t) => (
          <tr key={t.id}>
            <td className={`${td} mono`}>{t.pattern}</td>
            <td className={`${td} mono text-xs`}>{fmt(t.pages)}</td>
            {vitals.map((v) => {
              const val = t.cwv[v.key];
              return (
                <td key={v.key} className={td}>
                  <div className="flex items-center gap-2">
                    <span className="mono w-14 text-xs" style={{ color: color(val, v.good, v.poor) }}>{val}{v.unit}</span>
                    <div className="w-20"><Bar value={val} max={v.max} color={color(val, v.good, v.poor)} /></div>
                  </div>
                </td>
              );
            })}
            <td className={`${td} text-xs text-[var(--muted)]`}>{t.pages > 300 ? "Field (CrUX)" : "Lab (PSI)"}</td>
          </tr>
        ))}
      </Table>
      <p className="mt-3 text-xs text-[var(--faint)]">PageSpeed Insights is free (with a free API key for higher quota). Core Web Vitals are a Google ranking signal, and slow pages are crawled less.</p>
    </div>
  );
}

export function AiReadiness() {
  const blocked = AI_CRAWLERS.filter((c) => c.kind === "retrieval" && !c.allowed);
  return (
    <div className="space-y-6">
      <ModuleHead num={4} access="claude" title="AI readiness" desc="Can answer engines read, trust and quote these pages? Rule checks are free; the fact-extraction test uses Claude Haiku on sample pages." />
      {blocked.length > 0 && (
        <Notice title={`${blocked.map((b) => b.agent).join(", ")} blocked in robots.txt`}>
          Retrieval bots fetch pages to answer live questions. Blocking them removes the site from those answers. Training bots are a separate choice.
        </Notice>
      )}
      <Table head={["Template", "JSON-LD", "Fresh dateModified", "Verdict sentence", "Answer first", "Title matches intent", "Facts extracted"]} minWidth={820}>
        {AI_ROWS.map((r) => (
          <tr key={r.pattern}>
            <td className={`${td} mono`}>{r.pattern}</td>
            <td className={td}><span className={`pill ${r.jsonld === "valid" ? "bg-[var(--good-soft)] text-[var(--good)]" : r.jsonld === "invalid" ? "sev-medium" : "sev-high"}`}>{r.jsonld}</span></td>
            <td className={`${td} text-center`}><Check ok={r.fresh} /></td>
            <td className={`${td} text-center`}><Check ok={r.verdict} /></td>
            <td className={`${td} text-center`}><Check ok={r.answerFirst} /></td>
            <td className={`${td} text-center`}><Check ok={r.titleIntent} /></td>
            <td className={td}>
              <div className="flex items-center gap-2">
                <span className="mono w-10 text-xs" style={{ color: scoreColor(r.facts * 100) }}>{Math.round(r.facts * 100)}%</span>
                <div className="w-16"><Bar value={r.facts * 100} /></div>
              </div>
            </td>
          </tr>
        ))}
      </Table>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <div className="mb-3 text-sm font-medium">AI crawler policy (robots.txt)</div>
          <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm">
            {AI_CRAWLERS.map((c) => (
              <li key={c.agent} className="flex items-center justify-between gap-2">
                <span className="mono truncate text-xs">{c.agent}</span>
                <span className={`text-xs ${c.allowed ? "text-[var(--good)]" : c.kind === "retrieval" ? "text-[var(--bad)]" : "text-[var(--muted)]"}`}>
                  {c.allowed ? "allowed" : "blocked"} · {c.kind}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <div className="card p-4">
          <div className="mb-1 text-sm font-medium">llms.txt</div>
          <p className="text-sm text-[var(--bad)]">{LLMS_TXT.issues[0]}</p>
          <p className="mt-2 text-sm text-[var(--muted)]">A short markdown file that tells AI assistants what the site is and which pages matter. A generated one is ready in Fixes.</p>
        </div>
      </div>
    </div>
  );
}

export function WhatAiSees() {
  const [sel, setSel] = useState(RENDER_DIFFS[0].pattern);
  const d = RENDER_DIFFS.find((x) => x.pattern === sel)!;
  const share = 1 - d.rawWords / d.renderedWords;
  return (
    <div>
      <ModuleHead num={7} access="free" title="What AI sees" desc="Most AI crawlers don't run JavaScript. Each template is fetched twice: raw HTML, the way GPTBot and ClaudeBot see it, and fully rendered in a headless browser, the way you see it." />
      <div className="mb-4 flex flex-wrap gap-1.5">
        {RENDER_DIFFS.map((x) => (
          <button key={x.pattern} onClick={() => setSel(x.pattern)} className={`mono rounded-md border px-2.5 py-1 text-xs ${sel === x.pattern ? "border-[var(--text)]" : "border-[var(--line)] text-[var(--muted)]"}`}>{x.pattern}</button>
        ))}
      </div>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Text hidden behind JavaScript" value={`${Math.round(share * 100)}%`} color={share > 0.3 ? "var(--bad)" : "var(--good)"} note={`${fmt(d.rawWords)} of ${fmt(d.renderedWords)} words visible without JS`} />
        <Stat label="Links visible without JS" value={`${d.rawLinks} / ${d.renderedLinks}`} note="AI crawlers follow raw links only" />
        <Stat label="JSON-LD without JS" value={d.jsonldRaw ? "Yes" : "No"} color={d.jsonldRaw ? "var(--good)" : "var(--bad)"} note={d.jsonldRendered && !d.jsonldRaw ? "Injected client-side — invisible to most bots" : "Server-rendered"} />
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between text-sm font-medium">Raw HTML <span className="pill sev-low">GPTBot · ClaudeBot · PerplexityBot</span></div>
          <div className="space-y-2">
            <div className="h-3 w-3/4 rounded bg-[var(--sunken)]" /><div className="h-3 w-1/2 rounded bg-[var(--sunken)]" />
            <div className="rounded-md border border-dashed border-[var(--bad)]/50 p-3 text-xs text-[var(--bad)]">Missing: {d.jsOnly.length ? d.jsOnly.join(", ") : "nothing"}</div>
            <div className="h-3 w-2/3 rounded bg-[var(--sunken)]" />
          </div>
        </div>
        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between text-sm font-medium">Rendered <span className="pill sev-low">Chrome · Googlebot</span></div>
          <div className="space-y-2">
            <div className="h-3 w-3/4 rounded bg-[var(--sunken)]" /><div className="h-3 w-1/2 rounded bg-[var(--sunken)]" />
            <div className="rounded-md border border-[var(--good)]/40 bg-[var(--good-soft)] p-3 text-xs text-[var(--good)]">Present: {d.jsOnly.length ? d.jsOnly.join(", ") : "same as raw"}</div>
            <div className="h-3 w-2/3 rounded bg-[var(--sunken)]" />
          </div>
        </div>
      </div>
      {d.jsOnly.length > 0 && <p className="mt-4 text-sm text-[var(--muted)]">Fix: server-render these sections (SSR or static generation) so they're in the first HTML response.</p>}
    </div>
  );
}

export function Fixes() {
  return (
    <div className="space-y-6">
      <ModuleHead num={12} access="claude" title="Fixes" desc="Generated per template and checked before they're shown: JSON-LD is validated against schema.org, and placeholders map to your template's data fields." />
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <div className="mb-2 text-sm font-medium">Verdict sentence · /buildings/{"{slug}"}</div>
          <CodeBlock label="HTML · put near the top of the page" code={VERDICT_EXAMPLE} />
          <p className="mt-2 text-xs text-[var(--muted)]">One self-contained, factual sentence an answer engine can quote as-is.</p>
        </div>
        <div>
          <div className="mb-2 text-sm font-medium">Title template · /buildings/{"{slug}"}</div>
          <div className="card space-y-2 p-3 text-sm">
            <div><span className="text-xs text-[var(--faint)]">Before</span><div className="mono text-xs line-through decoration-[var(--bad)]">{TITLE_EXAMPLE.before}</div></div>
            <div><span className="text-xs text-[var(--faint)]">After</span><div className="mono text-xs text-[var(--good)]">{TITLE_EXAMPLE.after}</div></div>
            <p className="text-xs text-[var(--muted)]">{TITLE_EXAMPLE.why}</p>
          </div>
        </div>
        <div>
          <div className="mb-2 text-sm font-medium">llms.txt</div>
          <CodeBlock label="Save as /llms.txt" code={GENERATED_LLMS_TXT} />
        </div>
        <div>
          <div className="mb-2 text-sm font-medium">robots.txt</div>
          <CodeBlock label="Suggested robots.txt" code={GENERATED_ROBOTS} />
        </div>
      </div>
      <p className="text-xs text-[var(--faint)]">JSON-LD and summary-block fixes for each template are in Overview, under each template's findings.</p>
    </div>
  );
}
