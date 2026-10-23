"use client";

import { fmt } from "@/lib/mock";
import {
  ALERTS, CRAWL_COVERAGE, CRAWLER_HITS, CRAWLER_TEMPLATES, ENGINES, GAPS, GH_ACTION, MCP_CONFIG, MCP_TOOLS,
  RUNS, SHARE_OF_VOICE, VIS_ENGINES_LIVE, VIS_QUESTIONS,
} from "@/lib/modules";
import { Bar } from "@/components/Score";
import { CodeBlock, ModuleHead, Notice, Stat, Table, td } from "@/components/ui";

export function AiVisibility() {
  const live = ENGINES.filter((e) => VIS_ENGINES_LIVE[e]);
  const cells = VIS_QUESTIONS.flatMap((q) => live.map((e) => q.results[e])).filter(Boolean);
  const cited = cells.filter((c) => c!.cited).length;
  return (
    <div>
      <ModuleHead num={5} access="claude" title="AI visibility" desc="A fixed set of real questions, asked on a schedule. For each answer: is the site cited, where, and who is cited instead. Claude runs on the hosted demo; other engines use your own API keys." />
      <div className="mb-5 grid gap-2 sm:grid-cols-5">
        {ENGINES.map((e) => (
          <div key={e} className={`rounded-lg border px-3 py-2 text-sm ${VIS_ENGINES_LIVE[e] ? "border-[var(--accent)]/40 bg-[var(--accent-soft)]" : "border-dashed border-[var(--line-strong)]"}`}>
            <div className="font-medium">{e}</div>
            <div className="text-xs text-[var(--muted)]">{VIS_ENGINES_LIVE[e] ? "Live on the demo" : "Add your API key"}</div>
          </div>
        ))}
      </div>
      <Notice tone="key" title="ChatGPT, Perplexity, Gemini and Copilot columns are sample data">
        SEOGEO Audit Kit is open source. Self-host it and add <span className="mono">OPENAI_API_KEY</span>, <span className="mono">PERPLEXITY_API_KEY</span> or <span className="mono">GEMINI_API_KEY</span> to track those engines with the same metrics: cited or not, position in the answer, and competitors cited instead.
      </Notice>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Cited by Claude" value={`${cited} / ${cells.length}`} note="answers that link the site" />
        <Stat label="Share of voice" value="18%" note="of citations in this question set" />
        <Stat label="Question set" value={`${VIS_QUESTIONS.length} questions`} note="runs weekly · about $0.06 per run" />
      </div>
      <Table head={["Question", ...ENGINES, "Cited instead"]} minWidth={900}>
        {VIS_QUESTIONS.map((q) => (
          <tr key={q.q}>
            <td className={td}><div>{q.q}</div><div className="mono text-[11px] text-[var(--faint)]">{q.template}</div></td>
            {ENGINES.map((e) => {
              const c = q.results[e];
              return (
                <td key={e} className={`${td} text-center ${VIS_ENGINES_LIVE[e] ? "" : "opacity-60"}`}>
                  {!c ? <span className="text-[var(--faint)]">—</span> : c.cited ? <span className="pill bg-[var(--good-soft)] text-[var(--good)]">#{c.pos}</span> : <span className="text-[var(--bad)]">✕</span>}
                </td>
              );
            })}
            <td className={`${td} text-xs text-[var(--muted)]`}>{q.citedInstead.join(", ")}</td>
          </tr>
        ))}
      </Table>
      <div className="card mt-5 p-4">
        <div className="mb-3 text-sm font-medium">Share of voice</div>
        <ul className="space-y-2">
          {SHARE_OF_VOICE.map((s) => (
            <li key={s.domain} className="grid grid-cols-[160px_minmax(0,1fr)_48px] items-center gap-3 text-sm">
              <span className={`mono truncate text-xs ${s.you ? "font-semibold" : ""}`}>{s.domain}{s.you ? " (you)" : ""}</span>
              <Bar value={s.share * 100} max={30} color={s.you ? "var(--accent)" : "var(--line-strong)"} />
              <span className="mono text-right text-xs">{Math.round(s.share * 100)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function AiCrawlers() {
  return (
    <div>
      <ModuleHead num={6} access="free" title="AI crawlers" desc="From your server access logs: which bots crawl which templates, how often, and what errors they hit. Upload a log file or stream from Vercel, Cloudflare or nginx." />
      <Notice title="Sample: 30 days of logs (Vercel log drain)">Bots are identified by user agent and verified by reverse DNS where the operator publishes IP ranges, so spoofed bots are excluded.</Notice>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="AI bot requests" value={fmt(CRAWLER_HITS.filter((b) => b.kind !== "search").reduce((s, b) => s + b.hits.reduce((a, c) => a + c, 0), 0))} note="last 30 days" />
        <Stat label="Building pages seen by AI" value="29%" color="var(--bad)" note="71% never fetched by any AI bot" />
        <Stat label="Errors served to AI bots" value="1.6%" note="mostly 429 rate limits to ClaudeBot" />
      </div>
      <Table head={["Bot", "Type", ...CRAWLER_TEMPLATES, "Errors", "Last seen"]} minWidth={900}>
        {CRAWLER_HITS.map((b) => (
          <tr key={b.agent}>
            <td className={`${td} mono text-xs`}>{b.agent}</td>
            <td className={`${td} text-xs text-[var(--muted)]`}>{b.kind}</td>
            {b.hits.map((h, i) => <td key={i} className={`${td} mono text-xs ${h === 0 ? "text-[var(--faint)]" : ""}`}>{h ? fmt(h) : "0"}</td>)}
            <td className={`${td} mono text-xs`}>{b.errors ? `${(b.errors * 100).toFixed(1)}%` : "—"}</td>
            <td className={`${td} text-xs ${b.lastSeen.startsWith("Blocked") ? "text-[var(--bad)]" : "text-[var(--muted)]"}`}>{b.lastSeen}</td>
          </tr>
        ))}
      </Table>
      <div className="card mt-5 p-4">
        <div className="mb-3 text-sm font-medium">Share of each template's pages fetched by an AI bot (30 days)</div>
        <ul className="space-y-2">
          {CRAWL_COVERAGE.map((c) => (
            <li key={c.pattern} className="grid grid-cols-[200px_minmax(0,1fr)_48px] items-center gap-3">
              <span className="mono truncate text-xs">{c.pattern}</span>
              <Bar value={c.crawledByAI * 100} />
              <span className="mono text-right text-xs">{Math.round(c.crawledByAI * 100)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function Monitoring() {
  const w = 560, h = 140, pad = 24;
  const x = (i: number) => pad + (i / (RUNS.length - 1)) * (w - pad * 2);
  const y = (v: number) => h - pad - ((v - 40) / 50) * (h - pad * 2);
  const line = (k: "seo" | "ai") => RUNS.map((r, i) => `${Math.round(x(i))},${Math.round(y(r[k]))}`).join(" ");
  return (
    <div>
      <ModuleHead num={10} access="free" title="Monitoring" desc="Re-audits on a schedule and compares each template with the last run. When something regresses — schema removed, LCP up, a bot blocked — you get an alert with the pages affected." />
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Schedule" value="Weekly" note="Mondays 09:00 UTC · email + Slack" />
        <Stat label="Open alerts" value={String(ALERTS.length)} note="1 high severity" color="var(--bad)" />
        <Stat label="AI readiness trend" value="56 → 48" note="dropped after the Oct 17 deploy" color="var(--bad)" />
      </div>
      <div className="card p-4">
        <div className="mb-2 flex items-center justify-between text-sm font-medium">
          Score history
          <span className="flex gap-3 text-xs font-normal text-[var(--muted)]"><span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-[var(--good)]" />SEO</span><span className="flex items-center gap-1.5"><span className="h-0.5 w-4 bg-[var(--accent)]" />AI readiness</span></span>
        </div>
        <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Line chart: SEO score steady around 73, AI readiness fell from 56 to 48 in the last run">
          {[50, 70, 90].map((v) => <g key={v}><line x1={pad} x2={w - pad} y1={y(v)} y2={y(v)} stroke="var(--line)" /><text x={4} y={y(v) + 4} fontSize="10" fill="var(--faint)">{v}</text></g>)}
          <polyline points={line("seo")} fill="none" stroke="var(--good)" strokeWidth="2" />
          <polyline points={line("ai")} fill="none" stroke="var(--accent)" strokeWidth="2" />
          {RUNS.map((r, i) => <text key={r.date} x={x(i)} y={h - 6} fontSize="10" fill="var(--faint)" textAnchor="middle">{r.date}</text>)}
        </svg>
      </div>
      <ul className="mt-5 space-y-3">
        {ALERTS.map((a) => (
          <li key={a.title} className="card flex items-start gap-3 p-4">
            <span className={`pill sev-${a.severity} mt-0.5 capitalize`}>{a.severity}</span>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{a.title}</div>
              <div className="mt-0.5 text-sm text-[var(--muted)]">{a.detail}</div>
            </div>
            <div className="shrink-0 text-right text-xs text-[var(--faint)]"><div>{a.when}</div><div className="mono">{fmt(a.pages)} pages</div></div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function QuestionGaps() {
  const tone = (v: string) => (v === "yes" ? "text-[var(--good)]" : v === "partial" ? "text-[var(--warn)]" : "text-[var(--bad)]");
  return (
    <div>
      <ModuleHead num={13} access="claude" title="Question gaps" desc="Groups the questions people ask about your kind of site, maps each to the template that should answer it, and checks three things: does the page exist, does it answer, and can an AI pull the answer out." />
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Question families" value={String(GAPS.length)} note="from the visibility question set + Search Console queries" />
        <Stat label="No page at all" value={String(GAPS.filter((g) => !g.exists).length)} color="var(--bad)" note="new template opportunities" />
        <Stat label="Answer not extractable" value={String(GAPS.filter((g) => g.exists && g.extractable !== "yes").length)} color="var(--warn)" note="page exists, AI can't quote it" />
      </div>
      <Table head={["Priority", "Question family", "Template", "Page exists", "Answers it", "Extractable", "Fix"]} minWidth={900}>
        {GAPS.map((g) => (
          <tr key={g.family}>
            <td className={td}><span className={`pill ${g.priority === "P0" ? "sev-high" : g.priority === "P1" ? "sev-medium" : "sev-low"}`}>{g.priority}</span></td>
            <td className={td}><div>{g.family}</div><div className="text-xs text-[var(--faint)]">“{g.example}”</div></td>
            <td className={`${td} mono text-xs`}>{g.template}</td>
            <td className={`${td} text-xs ${g.exists ? "text-[var(--good)]" : "text-[var(--bad)]"}`}>{g.exists ? "yes" : "no"}</td>
            <td className={`${td} text-xs ${tone(g.answers)}`}>{g.answers}</td>
            <td className={`${td} text-xs ${tone(g.extractable)}`}>{g.extractable}</td>
            <td className={`${td} text-xs`}>{g.fix}</td>
          </tr>
        ))}
      </Table>
    </div>
  );
}

export function CiMcp() {
  return (
    <div className="space-y-6">
      <ModuleHead num={11} access="free" title="CI and MCP" desc="Catch SEO and GEO regressions before they ship, and run audits from your editor." />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="text-sm font-medium">GitHub Action</div>
          <CodeBlock label="Fails the PR when a template regresses" code={GH_ACTION} />
          <div className="card p-3">
            <div className="flex items-center gap-2 text-sm"><span className="grid h-5 w-5 place-items-center rounded-full bg-[var(--bad-soft)] text-xs text-[var(--bad)]">✕</span><span className="font-medium">SEOGEO Audit Kit</span><span className="text-[var(--muted)]">— 1 template regressed</span></div>
            <ul className="mono mt-2 space-y-1 pl-7 text-xs text-[var(--muted)]">
              <li>/buildings/{"{slug}"}: JSON-LD missing on 5/5 preview samples</li>
              <li>/buildings/{"{slug}"}: AI readiness 56 → 31 (limit −5)</li>
              <li className="text-[var(--good)]">5 other templates unchanged</li>
            </ul>
          </div>
        </div>
        <div className="space-y-3">
          <div className="text-sm font-medium">MCP server</div>
          <CodeBlock label="Claude Code / Cursor config" code={MCP_CONFIG} />
          <Table head={["Tool", "What it does"]} minWidth={0}>
            {MCP_TOOLS.map(([n, d]) => <tr key={n}><td className={`${td} mono text-xs`}>{n}</td><td className={`${td} text-xs text-[var(--muted)]`}>{d}</td></tr>)}
          </Table>
        </div>
      </div>
      <p className="text-xs text-[var(--faint)]">The action runs on your CI with your own key, so it costs the hosted demo nothing. Score drops use the same checks as the full audit, limited to the templates a PR touches.</p>
    </div>
  );
}

