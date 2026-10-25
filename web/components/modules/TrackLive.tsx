"use client";

import Link from "next/link";
import type { Audit } from "@/lib/mock";
import { fmt } from "@/lib/mock";
import { ENGINES } from "@/lib/modules";
import { Bar, scoreColor } from "@/components/Score";
import { ModuleHead, Notice, Stat, Table, td } from "@/components/ui";

const STATUS: Record<string, { label: string; cls: string }> = {
  cited: { label: "Cited", cls: "bg-[var(--good-soft)] text-[var(--good)]" },
  found: { label: "Found, not cited", cls: "sev-medium" },
  missing: { label: "Not found", cls: "sev-high" },
  not_searched: { label: "No search · not scored", cls: "sev-low" },
};

export function AiVisibilityLive({ audit }: { audit: Audit }) {
  const v = audit.live!.visibility!;
  return (
    <div>
      <ModuleHead num={5} access="claude" title="AI visibility" desc="Real questions about this site's pages, asked to Claude with web search. For each answer: is the site cited, did it come up in the search but get passed over, and who was cited instead." />
      <div className="mb-5 grid gap-2 sm:grid-cols-5">
        {ENGINES.map((e) => (
          <div key={e} className={`rounded-lg border px-3 py-2 text-sm ${e === "Claude" ? "border-[var(--accent)]/40 bg-[var(--accent-soft)]" : "border-dashed border-[var(--line-strong)]"}`}>
            <div className="font-medium">{e}</div>
            <div className="text-xs text-[var(--muted)]">{e === "Claude" ? `Cited in ${v.cited ?? 0} of ${v.asked ?? 0}` : "Add your API key (self-hosted)"}</div>
          </div>
        ))}
      </div>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Visibility score" value={v.score != null ? String(v.score) : "—"} color={v.score != null ? scoreColor(v.score) : undefined} note="cited = 1, found but not cited = ¼" />
        <Stat label="Cited by Claude" value={`${v.cited ?? 0} / ${v.asked ?? 0}`} note={`${v.found_not_cited ?? 0} found in search but not cited`} />
        <Stat label="Share of voice" value={`${Math.round(((v.share_of_voice.find((s) => s.you)?.share) ?? 0) * 100)}%`} note="of citations across these answers" />
      </div>
      <Table head={["Question", "Page type", "Result", "Cited instead"]} minWidth={760}>
        {v.answers.map((a) => (
          <tr key={a.question}>
            <td className={td}>
              <div>{a.question}</div>
              <details className="mt-1 text-xs text-[var(--faint)]"><summary className="cursor-pointer">Claude's answer</summary><p className="mt-1 whitespace-pre-line text-[var(--muted)]">{a.answer}</p></details>
            </td>
            <td className={`${td} mono text-[11px] text-[var(--muted)]`}>{a.page_type}</td>
            <td className={td}><span className={`pill ${STATUS[a.status].cls}`}>{STATUS[a.status].label}{a.position ? ` · #${a.position}` : ""}</span></td>
            <td className={`${td} text-xs text-[var(--muted)]`}>{a.cited_instead.join(", ") || "—"}</td>
          </tr>
        ))}
      </Table>
      {v.share_of_voice.length > 0 && (
        <div className="card mt-5 p-4">
          <div className="mb-3 text-sm font-medium">Share of voice</div>
          <ul className="space-y-2">
            {v.share_of_voice.map((s) => (
              <li key={s.domain} className="grid grid-cols-[160px_minmax(0,1fr)_48px] items-center gap-3 text-sm">
                <span className={`mono truncate text-xs ${s.you ? "font-semibold" : ""}`}>{s.domain}{s.you ? " (you)" : ""}</span>
                <Bar value={s.share * 100} max={Math.max(30, ...v.share_of_voice.map((x) => x.share * 100))} color={s.you ? "var(--accent)" : "var(--line-strong)"} />
                <span className="mono text-right text-xs">{Math.round(s.share * 100)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="mt-3 text-xs text-[var(--faint)]">ChatGPT, Perplexity, Gemini and Copilot use the same questions and metrics when you self-host with their API keys.</p>
    </div>
  );
}

export function QuestionGapsLive({ audit }: { audit: Audit }) {
  const gaps = audit.live!.gaps;
  const tone = (v: string | null) => (v === "yes" || v === "cited" ? "text-[var(--good)]" : v === "partial" || v === "found" ? "text-[var(--warn)]" : v ? "text-[var(--bad)]" : "text-[var(--faint)]");
  const label = (v: string | null) => (v === "found" ? "found, not cited" : v === "missing" ? "not cited" : v ?? "not asked");
  return (
    <div>
      <ModuleHead num={13} access="claude" title="Question gaps" desc="Questions people ask about each page type, from Claude's page checks: does the page answer it, can AI pull the facts out, and does AI cite the site for it?" />
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Questions" value={String(gaps.length)} note={`across ${new Set(gaps.map((g) => g.page_type)).size} page types`} />
        <Stat label="Not answered on the page" value={String(gaps.filter((g) => g.answered_on_page === "no").length)} color="var(--bad)" note="content to add" />
        <Stat label="Answered but not cited" value={String(gaps.filter((g) => g.answered_on_page !== "no" && g.ai_cites_site && g.ai_cites_site !== "cited").length)} color="var(--warn)" note="make the answer easier to quote" />
      </div>
      <Table head={["Question", "Page type", "Page answers it", "Facts extractable", "AI cites site"]} minWidth={820}>
        {gaps.map((g, i) => (
          <tr key={i}>
            <td className={td}>{g.question}</td>
            <td className={`${td} mono text-[11px] text-[var(--muted)]`}>{g.page_type}</td>
            <td className={`${td} text-xs ${tone(g.answered_on_page)}`}>{g.answered_on_page}</td>
            <td className={`${td} mono text-xs`}>{g.facts_extractable != null ? `${Math.round(g.facts_extractable * 100)}%` : "—"}</td>
            <td className={`${td} text-xs ${tone(g.ai_cites_site)}`}>{label(g.ai_cites_site)}</td>
          </tr>
        ))}
      </Table>
    </div>
  );
}

export function MonitoringLive({ audit }: { audit: Audit }) {
  const m = audit.live!.monitoring!;
  const trend = m.trend.filter((t) => t.geo != null || t.seo != null);
  const w = 560, h = 140, pad = 24;
  const x = (i: number) => pad + (trend.length > 1 ? (i / (trend.length - 1)) * (w - pad * 2) : (w - pad * 2) / 2);
  const y = (v: number) => h - pad - ((v - 0) / 100) * (h - pad * 2);
  const line = (k: "seo" | "geo" | "ai") => trend.filter((t) => t[k] != null).map((t) => `${Math.round(x(trend.indexOf(t)))},${Math.round(y(t[k]!))}`).join(" ");
  const real = m.changes.filter((c) => c.kind !== "fixed");
  const fixed = m.changes.filter((c) => c.kind === "fixed");
  return (
    <div>
      <ModuleHead num={10} access="free" title="Monitoring" desc="Each audit is compared with this site's previous one: score drops, new and fixed issues, newly blocked AI bots. Schedule re-audits to catch regressions after deploys." />
      {!m.previous_id ? (
        <Notice title="This is the first saved audit of this site">Run it again later (or schedule it below) and this page shows what changed.</Notice>
      ) : (
        <div className="mb-5 grid gap-3 sm:grid-cols-3">
          <Stat label="Compared with" value={new Date((m.previous_at ?? 0) * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })} note="the previous saved audit" />
          <Stat label="Regressions" value={String(real.length)} color={real.length ? "var(--bad)" : "var(--good)"} note={`${real.filter((c) => c.severity === "high").length} high severity`} />
          <Stat label="Fixed" value={String(fixed.length)} color="var(--good)" note="issues gone since last time" />
        </div>
      )}
      {m.previous_id && <Link href={`/report/${m.previous_id}`} className="-mt-2 mb-5 inline-block text-xs text-[var(--muted)] underline">Open the previous report</Link>}
      {trend.length > 1 && (
        <div className="card mb-5 p-4">
          <div className="mb-2 flex items-center justify-between text-sm font-medium">
            Score history
            <span className="flex gap-3 text-xs font-normal text-[var(--muted)]"><span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-[var(--accent)]" />GEO</span><span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-[var(--good)]" />SEO</span></span>
          </div>
          <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Line chart of GEO and SEO scores across saved audits">
            {[50, 75, 100].map((v) => <g key={v}><line x1={pad} x2={w - pad} y1={y(v)} y2={y(v)} stroke="var(--line)" /><text x={2} y={y(v) + 4} fontSize="10" fill="var(--faint)">{v}</text></g>)}
            <polyline points={line("seo")} fill="none" stroke="var(--good)" strokeWidth="2" />
            <polyline points={line("geo")} fill="none" stroke="var(--accent)" strokeWidth="2" />
            {trend.map((t, i) => <text key={t.id} x={x(i)} y={h - 6} fontSize="10" fill="var(--faint)" textAnchor="middle">{new Date(t.at * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })}</text>)}
          </svg>
        </div>
      )}
      {m.changes.length > 0 && (
        <ul className="space-y-3">
          {m.changes.map((c, i) => (
            <li key={i} className="card flex items-start gap-3 p-4">
              <span className={`pill ${c.kind === "fixed" ? "bg-[var(--good-soft)] text-[var(--good)]" : `sev-${c.severity}`} mt-0.5`}>{c.kind === "fixed" ? "Fixed" : c.severity}</span>
              <div className="min-w-0 flex-1"><div className="text-sm font-medium">{c.title}</div>{c.detail && <div className="mt-0.5 text-sm text-[var(--muted)]">{c.detail}</div>}</div>
              {c.pages > 0 && <span className="mono shrink-0 text-xs text-[var(--faint)]">{fmt(c.pages)} pages</span>}
            </li>
          ))}
        </ul>
      )}
      <div className="sunken mt-5 p-4 text-sm">
        <div className="font-medium">Scheduled re-audits</div>
        <p className="mt-1 text-[var(--muted)]">
          {m.monitors.length
            ? `This site is re-audited every ${m.monitors[0].every_hours} hours.`
            : "Not scheduled yet. Create one with the API — regressions can post to a Slack webhook:"}
        </p>
        {!m.monitors.length && <pre className="mono mt-2 overflow-x-auto text-xs text-[var(--muted)]">{`curl -X POST $API/monitors -H 'Content-Type: application/json' \\\n  -d '{"url": "${audit.site}", "every_hours": 168, "webhook_url": "https://hooks.slack.com/…"}'`}</pre>}
      </div>
    </div>
  );
}
