"use client";

import { fmt } from "@/lib/mock";
import { BING_ROWS, ENGINE_COLORS, ENGINES, TRAFFIC_BY_TEMPLATE, TRAFFIC_TREND, TRAFFIC_WEEKS } from "@/lib/modules";
import { Bar, scoreColor } from "@/components/Score";
import { ModuleHead, Notice, Sparkline, Stat, Table, td } from "@/components/ui";

export function Bing() {
  const sum = BING_ROWS.reduce((s, r) => ({ sub: s.sub + r.submitted, bing: s.bing + r.bing }), { sub: 0, bing: 0 });
  return (
    <div>
      <ModuleHead num={8} access="connect" title="Bing Webmaster" desc="ChatGPT search relies heavily on Bing's index, so a page Bing hasn't indexed rarely shows up in ChatGPT answers. Connect with a free Bing Webmaster API key." />
      <Notice tone="connect" title="Connected to Bing Webmaster · nestlist.example">Sample data. In your own install, paste a Bing Webmaster API key in Settings.</Notice>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="Indexed in Bing" value={`${Math.round((sum.bing / sum.sub) * 100)}%`} color={scoreColor((sum.bing / sum.sub) * 100)} note={`${fmt(sum.bing)} of ${fmt(sum.sub)}`} />
        <Stat label="Gap vs Google" value={fmt(BING_ROWS.reduce((s, r) => s + r.google - r.bing, 0))} note="pages Google indexed but Bing didn't" />
        <Stat label="Worst template" value="/buildings" note="15% indexed in Bing" />
      </div>
      <Table head={["Template", "Submitted", "Bing", "Google", "Bing coverage"]}>
        {BING_ROWS.map((r) => {
          const pct = (r.bing / r.submitted) * 100;
          return (
            <tr key={r.pattern}>
              <td className={`${td} mono`}>{r.pattern}</td>
              <td className={`${td} mono text-xs`}>{fmt(r.submitted)}</td>
              <td className={`${td} mono text-xs`}>{fmt(r.bing)}</td>
              <td className={`${td} mono text-xs text-[var(--muted)]`}>{fmt(r.google)}</td>
              <td className={td}><div className="flex items-center gap-2"><span className="mono w-10 text-xs" style={{ color: scoreColor(pct) }}>{Math.round(pct)}%</span><div className="w-28"><Bar value={pct} /></div></div></td>
            </tr>
          );
        })}
      </Table>
      <p className="mt-3 text-xs text-[var(--faint)]">Tip: submit the sitemap in Bing Webmaster and enable IndexNow so new pages are picked up within hours.</p>
    </div>
  );
}

export function AiTraffic() {
  const last = ENGINES.map((e) => TRAFFIC_TREND[e][TRAFFIC_TREND[e].length - 1]);
  const prev = ENGINES.map((e) => TRAFFIC_TREND[e][TRAFFIC_TREND[e].length - 2]);
  const total = last.reduce((a, b) => a + b, 0);
  const growth = total / prev.reduce((a, b) => a + b, 0) - 1;
  const weekly = TRAFFIC_WEEKS.map((_, i) => ENGINES.map((e) => TRAFFIC_TREND[e][i]));
  const maxWeek = Math.max(...weekly.map((w) => w.reduce((a, b) => a + b, 0)));
  return (
    <div>
      <ModuleHead num={9} access="connect" title="AI referral traffic" desc="Visits that arrive from AI answers (chatgpt.com, perplexity.ai, gemini.google.com, claude.ai, copilot), split by template. Connect GA4 or PostHog, read-only." />
      <Notice tone="connect" title="Connected to PostHog · project nestlist-web">Sample data. In your own install, connect GA4 or PostHog in Settings.</Notice>
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        <Stat label="AI visits last week" value={fmt(total)} note={`${growth >= 0 ? "+" : ""}${Math.round(growth * 100)}% vs the week before`} color="var(--good)" />
        <Stat label="Top engine" value="ChatGPT" note={`${Math.round((last[0] / total) * 100)}% of AI visits`} />
        <Stat label="Converts best" value="/buildings" note="4.1% of AI visitors apply" />
      </div>
      <div className="card p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm font-medium">Weekly AI visits by engine</span>
          <div className="flex flex-wrap gap-3 text-xs text-[var(--muted)]">
            {ENGINES.map((e) => <span key={e} className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: ENGINE_COLORS[e] }} />{e}</span>)}
          </div>
        </div>
        <div className="flex h-44 items-end gap-2" role="img" aria-label="Stacked bar chart of weekly AI referral visits by engine, rising over eight weeks">
          {weekly.map((w, i) => (
            <div key={i} className="flex flex-1 flex-col items-center gap-1">
              <div className="flex w-full flex-col-reverse overflow-hidden rounded-sm" style={{ height: `${(w.reduce((a, b) => a + b, 0) / maxWeek) * 150}px` }}>
                {w.map((v, j) => <div key={j} style={{ height: `${(v / w.reduce((a, b) => a + b, 0)) * 100}%`, background: ENGINE_COLORS[ENGINES[j]] }} />)}
              </div>
              <span className="text-[10px] text-[var(--faint)]">{TRAFFIC_WEEKS[i]}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-5">
        <Table head={["Template", "AI visits (28 days)", "Trend", "Conversion"]}>
          {TRAFFIC_BY_TEMPLATE.map((r, i) => (
            <tr key={r.pattern}>
              <td className={`${td} mono`}>{r.pattern}</td>
              <td className={`${td} mono`}>{fmt(r.visits)}</td>
              <td className={td}><Sparkline values={TRAFFIC_TREND.ChatGPT.map((v, k) => v * (1 - i * 0.12) + k * 3 * (5 - i))} /></td>
              <td className={`${td} mono text-xs`}>{(r.conv * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </Table>
      </div>
    </div>
  );
}
