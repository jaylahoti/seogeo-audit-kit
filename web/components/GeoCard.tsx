"use client";

import type { GeoScore } from "@/lib/mock";
import { Bar, ScoreRing, scoreColor } from "@/components/Score";

const PARTS = [
  ["access", "Access", "Can AI bots reach and read the pages?", "30%"],
  ["readiness", "Readiness", "Can AI understand and quote them?", "40%"],
  ["visibility", "Visibility", "Does AI actually cite the site?", "30%"],
] as const;

export function GeoCard({ geo }: { geo: GeoScore }) {
  const value = (k: (typeof PARTS)[number][0]) => (k === "access" ? geo.access.score : k === "readiness" ? geo.readiness.score : geo.visibility.score);
  return (
    <div className="card p-5">
      <div className="grid items-center gap-6 md:grid-cols-[auto_minmax(0,1fr)]">
        <div className="flex items-center gap-4">
          <ScoreRing value={geo.score ?? 0} label="" size={96} />
          <div>
            <div className="text-lg font-semibold">GEO score</div>
            <div className="text-xs text-[var(--muted)]">How well AI search finds, reads and cites the site</div>
            {geo.partial && <span className="pill sev-medium mt-1.5">Partial · Visibility pending</span>}
          </div>
        </div>
        <ul className="space-y-3">
          {PARTS.map(([k, label, q, w]) => {
            const v = value(k);
            return (
              <li key={k} className="grid grid-cols-[92px_minmax(0,1fr)_44px] items-center gap-3 text-sm">
                <span><span className="font-medium">{label}</span> <span className="text-[11px] text-[var(--faint)]">{w}</span></span>
                <span className="min-w-0">
                  {v == null ? <span className="block truncate text-xs text-[var(--faint)]">{geo.visibility.reason ?? "Pending"}</span> : <Bar value={v} />}
                  <span className="mt-0.5 block truncate text-[11px] text-[var(--faint)]">{q}</span>
                </span>
                <span className="mono text-right" style={{ color: v == null ? "var(--faint)" : scoreColor(v) }}>{v ?? "—"}</span>
              </li>
            );
          })}
        </ul>
      </div>

      <details className="group mt-4 border-t border-[var(--line)] pt-3">
        <summary className="flex cursor-pointer list-none items-center justify-between text-xs text-[var(--muted)]">
          What's in the score <span className="text-[var(--faint)] transition group-open:rotate-45">+</span>
        </summary>
        <div className="mt-3 grid gap-4 text-sm md:grid-cols-3">
          <div>
            <div className="text-xs font-medium">Access {geo.access.score}</div>
            {geo.access.signals.length ? (
              <ul className="mt-1.5 space-y-1.5">
                {geo.access.signals.map((s) => (
                  <li key={s.label} className="flex gap-2 text-xs">
                    <span className={`mono w-8 shrink-0 text-right ${s.impact < 0 ? "text-[var(--bad)]" : "text-[var(--warn)]"}`}>{s.impact < 0 ? s.impact : "!"}</span>
                    <span><span className="text-[var(--text)]">{s.label}</span><span className="block text-[var(--faint)]">{s.detail}</span></span>
                  </li>
                ))}
              </ul>
            ) : <p className="mt-1.5 text-xs text-[var(--good)]">No access problems found.</p>}
          </div>
          <div>
            <div className="text-xs font-medium">Readiness {geo.readiness.score ?? "—"}</div>
            <p className="mt-1.5 text-xs text-[var(--faint)]">
              The AI-readiness checks per template (structured data, freshness, verdict sentences, facts up front, empty values), weighted by pages.
              {geo.readiness.method === "rules" && " Claude's fact-extraction test is added once the Claude checks run."}
            </p>
          </div>
          <div>
            <div className="text-xs font-medium">Visibility {geo.visibility.score ?? "— pending"}</div>
            {geo.visibility.engines ? (
              <ul className="mt-1.5 space-y-1 text-xs">
                {geo.visibility.engines.map((e) => (
                  <li key={e.name} className="flex justify-between gap-2">
                    <span>{e.name}{!e.live && <span className="text-[var(--faint)]"> · your key</span>}</span>
                    <span className="mono">{e.cited}/{e.asked} cited</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1.5 text-xs text-[var(--faint)]">Claude asks the questions each template should answer, with web search, and records whether the site is cited. Other engines use your own keys.</p>
            )}
          </div>
        </div>
        <p className="mt-3 text-[11px] text-[var(--faint)]">GEO = Access 30% + Readiness 40% + Visibility 30%. Parts that haven't run yet are left out and the weights rescaled.</p>
      </details>
    </div>
  );
}
