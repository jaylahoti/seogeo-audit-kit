"use client";

import { useEffect, useRef, useState } from "react";
import type { Template } from "@/lib/mock";
import { fmt } from "@/lib/mock";
import { scoreColor } from "@/components/Score";

const r1 = (v: number) => Math.round(v * 10) / 10; // same SVG attributes on server and client
const short = (p: string) => p.replace(/ · layout \d+$/, "").replace(/\{[a-z]+\}/g, "…");
const compact = (v: number) => (v >= 1e6 ? `${v / 1e6}M` : v >= 1e3 ? `${v / 1e3}K` : String(v));
const health = (t: Template) => Math.round((t.seo + t.ai) / 2);
const weight = (t: Template) => t.findings.reduce((n, f) => n + (f.severity === "high" ? 3 : f.severity === "medium" ? 2 : 1), 0);

/**
 * Each page type as a dot: right = healthier, up = more pages, bigger = more issues.
 * Top-left (big and unhealthy) is where one template fix helps the most pages.
 */
export function WhereToStart({ templates, onPick }: { templates: Template[]; onPick?: (id: string) => void }) {
  const [hover, setHover] = useState<string | null>(null);
  // Draw at the real width so text stays readable on phones (640 until measured, same on server and client).
  const box = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(640);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(300, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const ts = templates.filter((t) => t.pages > 0 && (t.seo > 0 || t.ai > 0));
  if (ts.length < 2) return null;

  const H = W < 480 ? 260 : 300, L = 46, R = 12, T = 14, B = 40;
  const lo = Math.log10(Math.max(1, Math.min(...ts.map((t) => t.pages))));
  const hi = Math.log10(Math.max(...ts.map((t) => t.pages)));
  const span = Math.max(0.5, hi - lo);
  const x = (h: number) => L + (h / 100) * (W - L - R);
  const y = (pages: number) => T + (1 - (Math.log10(Math.max(1, pages)) - lo + span * 0.08) / (span * 1.16)) * (H - T - B);
  const maxW = Math.max(1, ...ts.map(weight));
  const rad = (t: Template) => 5 + 11 * Math.sqrt(weight(t) / maxW);
  const midY = y(10 ** ((lo + hi) / 2));
  const ticks = [1, 10, 100, 1e3, 1e4, 1e5, 1e6, 1e7].filter((v) => Math.log10(v) >= lo - span * 0.08 && Math.log10(v) <= hi + span * 0.08);
  // Label the biggest page types. Labels go left of dots on the right side (so they aren't cut off),
  // and a label is skipped if its box would overlap one already placed.
  type Lbl = { id: string; x: number; y: number; end: boolean; text: string; box: [number, number, number, number] };
  const labelOf = (t: Template): Lbl => {
    const cx = x(health(t)), cy = y(t.pages), text = short(t.pattern), w = text.length * 6.3, end = cx > W * 0.62;
    const lx = end ? cx - rad(t) - 4 : cx + rad(t) + 4;
    return { id: t.id, x: r1(lx), y: r1(cy + 3), end, text, box: [end ? lx - w : lx, cy - 7, end ? lx : lx + w, cy + 7] };
  };
  const hits = (a: Lbl["box"], b: Lbl["box"]) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
  const labels: Lbl[] = [];
  for (const t of [...ts].sort((a, b) => b.pages - a.pages).slice(0, W < 480 ? 3 : 5)) {
    const l = labelOf(t);
    if (!labels.some((o) => hits(o.box, l.box))) labels.push(l);
  }
  const fixFirst = ts.filter((t) => health(t) < 70 && y(t.pages) <= midY).length;

  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">Where to start</h3>
        <span className="text-xs text-[var(--muted)]">
          {fixFirst ? `${fixFirst} page type${fixFirst === 1 ? "" : "s"} in the “fix first” corner` : "No big, unhealthy page types"}
        </span>
      </div>
      <p className="mt-0.5 text-xs text-[var(--muted)]">Each dot is a page type. Right = healthier, up = more pages, bigger = more issues. Top-left is where one fix helps the most pages.</p>
      <div ref={box} className="mt-2 w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Page types by health and number of pages">
        <rect x={L} y={T} width={r1(x(70) - L)} height={r1(midY - T)} fill="var(--bad-soft)" opacity="0.7" rx="6" />
        <text x={L + 8} y={T + 16} fontSize="11" fill="var(--bad)" fontWeight="600">Fix first</text>
        {[0, 50, 70, 100].map((v) => (
          <g key={v}>
            <line x1={r1(x(v))} x2={r1(x(v))} y1={T} y2={H - B} stroke="var(--line)" strokeDasharray={v === 70 ? "3 3" : undefined} />
            <text x={r1(x(v))} y={H - B + 14} fontSize="10" fill="var(--faint)" textAnchor="middle">{v}</text>
          </g>
        ))}
        {ticks.map((v) => (
          <g key={v}>
            <line x1={L} x2={W - R} y1={r1(y(v))} y2={r1(y(v))} stroke="var(--line)" />
            <text x={L - 6} y={r1(y(v)) + 3} fontSize="10" fill="var(--faint)" textAnchor="end">{compact(v)}</text>
          </g>
        ))}
        <text x={r1((L + W - R) / 2)} y={H - 6} fontSize="10" fill="var(--muted)" textAnchor="middle">Health: average of SEO and AI readiness →</text>
        <text x={12} y={r1((T + H - B) / 2)} fontSize="10" fill="var(--muted)" textAnchor="middle" transform={`rotate(-90 12 ${r1((T + H - B) / 2)})`}>Pages →</text>
        {[...ts].sort((a, b) => weight(b) - weight(a)).map((t) => {
          const cx = r1(x(health(t))), cy = r1(y(t.pages)), on = hover === t.id;
          return (
            <g key={t.id} onMouseEnter={() => setHover(t.id)} onMouseLeave={() => setHover(null)} onClick={() => onPick?.(t.id)} style={{ cursor: onPick ? "pointer" : undefined }}>
              <title>{`${t.pattern} · ${fmt(t.pages)} pages · SEO ${t.seo}, AI readiness ${t.ai} · ${t.findings.length} issues`}</title>
              <circle cx={cx} cy={cy} r={r1(rad(t))} fill={scoreColor(health(t))} fillOpacity={hover && !on ? 0.25 : 0.75} stroke="var(--panel)" strokeWidth="1.5" />
            </g>
          );
        })}
        {/* Labels last, so they sit on top of the dots; the outline keeps them readable over anything. */}
        <g pointerEvents="none">
          {(hover && !labels.some((l) => l.id === hover) ? [...labels, labelOf(ts.find((t) => t.id === hover)!)] : labels).map((l) => (
            <text key={l.id} x={l.x} y={l.y} fontSize="10.5" fill="var(--text)" textAnchor={l.end ? "end" : "start"} className="mono"
              stroke="var(--panel)" strokeWidth="3" paintOrder="stroke" strokeLinejoin="round">{l.text}</text>
          ))}
        </g>
      </svg>
      </div>
    </div>
  );
}

/** Issues per page type, stacked by severity, for the largest page types. */
export function IssuesByType({ templates, onPick }: { templates: Template[]; onPick?: (id: string) => void }) {
  const ts = [...templates].filter((t) => t.findings.length).sort((a, b) => b.pages - a.pages).slice(0, 8);
  if (!ts.length) return null;
  const count = (t: Template, s: string) => t.findings.filter((f) => f.severity === s).length;
  const max = Math.max(...ts.map((t) => t.findings.length));
  const SEV = [["high", "var(--bad)"], ["medium", "var(--warn)"], ["low", "var(--line-strong)"]] as const;
  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">Issues by page type</h3>
        <span className="flex gap-3 text-[11px] text-[var(--muted)]">
          {SEV.map(([s, c]) => <span key={s} className="flex items-center gap-1"><span className="h-2 w-2 rounded-sm" style={{ background: c }} />{s}</span>)}
        </span>
      </div>
      <p className="mt-0.5 text-xs text-[var(--muted)]">The largest page types first. Fixing a page type&apos;s template fixes every page built from it.</p>
      <ul className="mt-3 space-y-2.5">
        {ts.map((t) => (
          <li key={t.id}>
            <button onClick={() => onPick?.(t.id)} className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 text-left text-xs hover:opacity-80">
              <span className="mono truncate" title={t.pattern}>{t.pattern}</span>
              <span className="mono text-[var(--faint)]">{fmt(t.pages)} pages</span>
              <span className="col-span-2 flex h-2.5 overflow-hidden rounded-full bg-[var(--sunken)]">
                {SEV.map(([s, c]) => {
                  const n = count(t, s);
                  return n ? <span key={s} title={`${n} ${s}`} style={{ width: `${(n / max) * 100}%`, background: c }} /> : null;
                })}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
