"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getAudit, streamEvents, type StageEvent } from "@/lib/api";
import { rememberAudit, siteOf } from "@/lib/recent";
import { fmt } from "@/lib/mock";
import { scoreColor } from "@/components/Score";

// The pipeline's stages in order, so upcoming ones can be shown before they start.
const PLAN: [string, string][] = [
  ["robots", "Read robots.txt"],
  ["llms_txt", "Check llms.txt"],
  ["sitemap", "Read sitemap"],
  ["templates", "Detect templates (URL patterns)"],
  ["crawl", "Crawl sample pages"],
  ["layouts", "Detect templates (HTML structure)"],
  ["checks", "SEO and AI-readiness checks"],
  ["links", "Link checks"],
  ["render", "What AI sees"],
  ["cwv", "Core Web Vitals"],
  ["claude_pages", "Claude page checks"],
  ["visibility", "AI visibility"],
  ["score", "Score and generate fixes"],
  ["judge", "Judge and write fixes"],
];
const CLAUDE_STEPS: Record<string, string> = { claude_pages: "Page checks · Haiku", visibility: "Visibility · Haiku + search", judge: "Judge · Sonnet" };

type StageState = { status: "waiting" | "running" | "done" | "error"; label: string; detail?: string; ms?: number };
type Tpl = { pattern: string; estimated_pages: number };

export function LiveRun({ id, url }: { id: string; url: string }) {
  const router = useRouter();
  const [stages, setStages] = useState<Record<string, StageState>>(
    Object.fromEntries(PLAN.map(([k, l]) => [k, { status: "waiting", label: l }])),
  );
  const [templates, setTemplates] = useState<Tpl[] | null>(null);
  const [scores, setScores] = useState<{ seo: number; ai: number; geo?: number | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [costs, setCosts] = useState<Record<string, { cost: number; calls: number; done: boolean }>>({});
  const [budget, setBudget] = useState<number | null>(null);
  const started = useRef(Date.now());

  useEffect(() => {
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - started.current) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    async function refresh() {
      const a = await getAudit(id).catch(() => null);
      if (a?.result?.templates) setTemplates(a.result.templates);
      if (a?.result?.scores) setScores({ ...a.result.scores, geo: a.result.geo?.score });
    }
    const stop = streamEvents(id, (e: StageEvent) => {
      if (e.type === "stage" && e.key) {
        setStages((s) => ({
          ...s,
          [e.key!]: { status: e.status as StageState["status"], label: e.label ?? s[e.key!]?.label ?? e.key!, detail: e.detail, ms: e.ms },
        }));
        if (e.key in CLAUDE_STEPS && e.status === "done") {
          setCosts((c) => ({ ...c, [e.key!]: { cost: e.cost ?? 0, calls: c[e.key!]?.calls ?? 0, done: true } }));
        }
        if (e.status === "done" && (e.key === "templates" || e.key === "layouts" || e.key === "score")) refresh();
      } else if (e.type === "progress" && e.key && e.key in CLAUDE_STEPS) {
        setCosts((c) => ({ ...c, [e.key!]: { cost: Number(e.cost ?? 0), calls: Number(e.calls ?? 0), done: false } }));
        if (e.budget != null) setBudget(Number(e.budget));
        setStages((s) => ({ ...s, [e.key!]: { ...s[e.key!], detail: `${e.calls} Claude calls so far · $${Number(e.cost).toFixed(3)}` } }));
      } else if (e.type === "progress" && e.key) {
        const detail = e.key === "sitemap" ? `${fmt(Number(e.urls))} URLs from ${e.sitemaps} sitemaps so far` : `${e.pages} of ${e.of} pages`;
        setStages((s) => ({ ...s, [e.key!]: { ...s[e.key!], detail } }));
      } else if (e.type === "done") {
        rememberAudit({ id, site: siteOf(url || ""), at: Date.now(), status: "done" });
        setDone(true);
        refresh();
        setTimeout(() => router.push(`/report/${encodeURIComponent(id)}`), 1500);
      } else if (e.type === "error") {
        rememberAudit({ id, site: siteOf(url || ""), at: Date.now(), status: "error" });
        setError(e.message ?? "The audit failed.");
      }
    });
    return stop;
  }, [id, router]);

  const order = [...PLAN.map(([k]) => k), ...Object.keys(stages).filter((k) => !PLAN.some(([p]) => p === k))];
  const finished = Object.values(stages).filter((s) => s.status === "done").length;

  return (
    <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 py-10 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section>
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-xs text-[var(--muted)]">Auditing · usually 2–3 minutes</p>
          <span className="mono text-xs text-[var(--faint)]">{Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, "0")}</span>
        </div>
        <h1 className="mono mt-1 truncate text-lg">{url}</h1>
        <div className="mt-3 h-1 overflow-hidden rounded-full bg-[var(--sunken)]">
          <div className="h-full rounded-full bg-[var(--accent)] transition-all" style={{ width: `${(finished / PLAN.length) * 100}%` }} />
        </div>

        <ol className="card mt-5 divide-y divide-[var(--line)]">
          {order.map((k) => {
            const s = stages[k];
            if (!s) return null;
            return (
              <li key={k} className="flex items-center gap-3 px-4 py-3">
                <span className="grid h-5 w-5 shrink-0 place-items-center">
                  {s.status === "done" && <span className="text-[var(--good)]">✓</span>}
                  {s.status === "error" && <span className="text-[var(--bad)]">✕</span>}
                  {s.status === "running" && <span className="spin block h-4 w-4 rounded-full border-2 border-[var(--line-strong)] border-t-[var(--accent)]" />}
                  {s.status === "waiting" && <span className="block h-2 w-2 rounded-full bg-[var(--line-strong)]" />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className={`text-sm ${s.status === "waiting" ? "text-[var(--faint)]" : ""}`}>{s.label}</div>
                  {s.detail && <div className="truncate text-xs text-[var(--muted)]">{s.detail}</div>}
                </div>
                <span className="mono w-16 text-right text-xs text-[var(--muted)]">{s.status === "done" && s.ms != null ? `${(s.ms / 1000).toFixed(1)}s` : ""}</span>
              </li>
            );
          })}
        </ol>

        {error && (
          <div className="fadein mt-4 rounded-xl border border-[var(--bad)]/30 bg-[var(--bad-soft)] px-4 py-3 text-sm">
            <div className="font-medium text-[var(--bad)]">{error}</div>
            <Link href="/" className="mt-1 inline-block text-[var(--muted)] underline">Try another URL</Link>
          </div>
        )}
        {done && (
          <div className="fadein mt-4 flex items-center justify-between rounded-xl border border-[var(--good)]/30 bg-[var(--good-soft)] px-4 py-3 text-sm">
            <span>Audit complete. Opening the report…</span>
            <Link href={`/report/${encodeURIComponent(id)}`} className="btn">Open report</Link>
          </div>
        )}
      </section>

      <aside className="space-y-4">
        <div className="card p-4">
          <div className="text-xs text-[var(--muted)]">Claude cost so far</div>
          <div className="mono mt-1 text-3xl font-semibold tabular-nums">${Object.values(costs).reduce((n, c) => n + c.cost, 0).toFixed(3)}</div>
          <ul className="mt-3 space-y-1.5 text-xs">
            {Object.entries(CLAUDE_STEPS).map(([k, label]) => {
              const c = costs[k];
              const st = stages[k]?.status;
              return (
                <li key={k} className="flex items-center justify-between gap-2">
                  <span className={st === "waiting" ? "text-[var(--faint)]" : ""}>{label}</span>
                  <span className="mono text-[var(--muted)]">
                    {c ? `${c.calls ? `${c.calls} calls · ` : ""}$${c.cost.toFixed(3)}` : st === "done" ? "skipped" : "—"}
                  </span>
                </li>
              );
            })}
          </ul>
          <div className="mt-3 text-[11px] text-[var(--faint)]">
            Everything else is code, ML and a headless browser: $0.{budget != null && ` Budget for this audit: $${budget.toFixed(2)}.`}
          </div>
        </div>
        <div className="card p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <span className="text-sm font-medium">Templates found</span>
            <span className="text-xs text-[var(--faint)]">{templates ? templates.length : "waiting…"}</span>
          </div>
          <ul className="space-y-2">
            {templates
              ? templates.slice(0, 12).map((t, i) => (
                  <li key={t.pattern + i} className="fadein flex items-center justify-between gap-2 text-sm" style={{ animationDelay: `${i * 60}ms` }}>
                    <span className="mono truncate">{t.pattern}</span>
                    <span className="mono text-xs text-[var(--muted)]">{fmt(t.estimated_pages)}</span>
                  </li>
                ))
              : Array.from({ length: 4 }).map((_, i) => <li key={i} className="h-4 animate-pulse rounded bg-[var(--sunken)]" />)}
          </ul>
          {scores && (
            <div className="fadein mt-4 flex gap-4 border-t border-[var(--line)] pt-3 text-sm">
              {scores.geo != null && <span>GEO <b style={{ color: scoreColor(scores.geo) }}>{scores.geo}</b></span>}
              <span>SEO <b style={{ color: scoreColor(scores.seo) }}>{scores.seo}</b></span>
              <span>AI <b style={{ color: scoreColor(scores.ai) }}>{scores.ai}</b></span>
            </div>
          )}
        </div>
      </aside>
    </main>
  );
}
