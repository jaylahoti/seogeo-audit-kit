"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { SAMPLE_AUDIT, fmt } from "@/lib/mock";
import { scoreColor } from "@/components/Score";

const STEP_MS = 900; // prototype pacing; the real run streams stage events over SSE

export function RunProgress() {
  const params = useSearchParams();
  const router = useRouter();
  const url = params.get("url") ?? SAMPLE_AUDIT.sitemap;
  const stages = SAMPLE_AUDIT.stages;
  const [done, setDone] = useState(0);

  useEffect(() => {
    if (done >= stages.length) {
      const t = setTimeout(() => router.push(`/report/${SAMPLE_AUDIT.id}`), 1800);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setDone((d) => d + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [done, stages.length, router]);

  const cost = stages.slice(0, done).reduce((s, x) => s + x.cost, 0);
  const clusterIdx = stages.findIndex((s) => s.key === "cluster");
  const showTemplates = done > clusterIdx;
  const finished = done >= stages.length;

  return (
    <main className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 py-10 lg:grid-cols-[minmax(0,1fr)_340px]">
      <section>
        <p className="text-xs text-[var(--muted)]">Auditing</p>
        <h1 className="mono mt-1 truncate text-lg">{url}</h1>

        <ol className="card mt-6 divide-y divide-[var(--line)]">
          {stages.map((s, i) => {
            const state = i < done ? "done" : i === done ? "running" : "waiting";
            return (
              <li key={s.key} className="flex items-center gap-3 px-4 py-3">
                <span className="grid h-5 w-5 shrink-0 place-items-center">
                  {state === "done" && <span className="text-[var(--good)]">✓</span>}
                  {state === "running" && <span className="spin block h-4 w-4 rounded-full border-2 border-[var(--line-strong)] border-t-[var(--accent)]" />}
                  {state === "waiting" && <span className="block h-2 w-2 rounded-full bg-[var(--line-strong)]" />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className={`text-sm ${state === "waiting" ? "text-[var(--faint)]" : ""}`}>{s.label}</div>
                  {state !== "waiting" && <div className="truncate text-xs text-[var(--muted)]">{s.detail}</div>}
                </div>
                {s.model && <span className="pill sev-low hidden sm:inline-flex">{s.model}</span>}
                <span className="mono w-16 text-right text-xs text-[var(--muted)]">
                  {state === "done" ? `${(s.ms / 1000).toFixed(1)}s` : ""}
                </span>
                <span className="mono w-14 text-right text-xs text-[var(--muted)]">
                  {state === "done" ? `$${s.cost.toFixed(3)}` : ""}
                </span>
              </li>
            );
          })}
        </ol>

        {finished && (
          <div className="fadein mt-4 flex items-center justify-between rounded-xl border border-[var(--good)]/30 bg-[var(--good-soft)] px-4 py-3 text-sm">
            <span>Audit complete. Opening the report…</span>
            <Link href={`/report/${SAMPLE_AUDIT.id}`} className="btn">Open report</Link>
          </div>
        )}
      </section>

      <aside className="space-y-4">
        <div className="card p-4">
          <div className="text-xs text-[var(--muted)]">Running cost</div>
          <div className="mono mt-1 text-3xl font-semibold tabular-nums">${cost.toFixed(3)}</div>
          <div className="mt-1 text-xs text-[var(--faint)]">Naive approach (every page through Sonnet): ${SAMPLE_AUDIT.naiveCost.toFixed(2)}</div>
        </div>

        <div className="card p-4">
          <div className="mb-3 flex items-baseline justify-between">
            <span className="text-sm font-medium">Templates found</span>
            <span className="text-xs text-[var(--faint)]">{showTemplates ? `${SAMPLE_AUDIT.templates.length} from ${fmt(SAMPLE_AUDIT.urls)} URLs` : "waiting…"}</span>
          </div>
          <ul className="space-y-2">
            {showTemplates
              ? SAMPLE_AUDIT.templates.map((t, i) => (
                  <li key={t.id} className="fadein flex items-center justify-between gap-2 text-sm" style={{ animationDelay: `${i * 90}ms` }}>
                    <span className="mono truncate">{t.pattern}</span>
                    <span className="mono text-xs text-[var(--muted)]">{fmt(t.pages)}</span>
                  </li>
                ))
              : Array.from({ length: 4 }).map((_, i) => <li key={i} className="h-4 animate-pulse rounded bg-[var(--sunken)]" />)}
          </ul>
          {finished && (
            <div className="fadein mt-4 flex gap-4 border-t border-[var(--line)] pt-3 text-sm">
              <span>SEO <b style={{ color: scoreColor(SAMPLE_AUDIT.scores.seo) }}>{SAMPLE_AUDIT.scores.seo}</b></span>
              <span>AI <b style={{ color: scoreColor(SAMPLE_AUDIT.scores.ai) }}>{SAMPLE_AUDIT.scores.ai}</b></span>
            </div>
          )}
        </div>
      </aside>
    </main>
  );
}
