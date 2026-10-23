"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { getAudit, streamEvents, type StageEvent } from "@/lib/api";
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
  ["score", "Score and generate fixes"],
];

type StageState = { status: "waiting" | "running" | "done" | "error"; label: string; detail?: string; ms?: number };
type Tpl = { pattern: string; estimated_pages: number };

export function LiveRun({ id, url }: { id: string; url: string }) {
  const router = useRouter();
  const [stages, setStages] = useState<Record<string, StageState>>(
    Object.fromEntries(PLAN.map(([k, l]) => [k, { status: "waiting", label: l }])),
  );
  const [templates, setTemplates] = useState<Tpl[] | null>(null);
  const [scores, setScores] = useState<{ seo: number; ai: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const started = useRef(Date.now());

  useEffect(() => {
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - started.current) / 1000)), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    async function refresh() {
      const a = await getAudit(id).catch(() => null);
      if (a?.result?.templates) setTemplates(a.result.templates);
      if (a?.result?.scores) setScores(a.result.scores);
    }
    const stop = streamEvents(id, (e: StageEvent) => {
      if (e.type === "stage" && e.key) {
        setStages((s) => ({
          ...s,
          [e.key!]: { status: e.status as StageState["status"], label: e.label ?? s[e.key!]?.label ?? e.key!, detail: e.detail, ms: e.ms },
        }));
        if (e.status === "done" && (e.key === "templates" || e.key === "layouts" || e.key === "score")) refresh();
      } else if (e.type === "progress" && e.key) {
        const detail = e.key === "sitemap" ? `${fmt(Number(e.urls))} URLs from ${e.sitemaps} sitemaps so far` : `${e.pages} of ${e.of} pages`;
        setStages((s) => ({ ...s, [e.key!]: { ...s[e.key!], detail } }));
      } else if (e.type === "done") {
        setDone(true);
        refresh();
        setTimeout(() => router.push(`/report/${encodeURIComponent(id)}`), 1500);
      } else if (e.type === "error") {
        setError(e.message ?? "The audit failed.");
      }
    });
    return stop;
  }, [id, router]);

  const order = [...PLAN.map(([k]) => k), ...Object.keys(stages).filter((k) => !PLAN.some(([p]) => p === k))];
  const finished = Object.values(stages).filter((s) => s.status === "done").length;

  return (
    <main className="mx-auto grid max-w-6xl gap-6 px-4 py-10 lg:grid-cols-[1fr_340px]">
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
          <div className="mono mt-1 text-3xl font-semibold tabular-nums">$0.000</div>
          <div className="mt-1 text-xs text-[var(--faint)]">This audit uses rules, ML and a headless browser only. Claude checks arrive next.</div>
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
              <span>SEO <b style={{ color: scoreColor(scores.seo) }}>{scores.seo}</b></span>
              <span>AI <b style={{ color: scoreColor(scores.ai) }}>{scores.ai}</b></span>
            </div>
          )}
        </div>
      </aside>
    </main>
  );
}
