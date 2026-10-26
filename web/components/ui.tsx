"use client";

import { useState } from "react";
import type { Access } from "@/lib/modules";
import { ACCESS_LABEL, COMING_SOON } from "@/lib/modules";

export function AccessBadge({ access }: { access: Access }) {
  const cls =
    access === "free" ? "sev-low"
    : access === "claude" ? "bg-[var(--accent-soft)] text-[var(--accent)]"
    : access === "connect" ? "bg-[var(--good-soft)] text-[var(--good)]"
    : "bg-[var(--warn-soft)] text-[var(--warn)]";
  return <span className={`pill ${cls}`}>{ACCESS_LABEL[access]}</span>;
}

export function SoonBadge() {
  return <span className="pill border border-dashed border-[var(--line-strong)] text-[var(--muted)]">Coming soon</span>;
}

export function ModuleHead({ title, desc, access, num, id }: { title: string; desc: string; access: Access; num?: number; id?: string }) {
  return (
    <div className="mb-5">
      <div className="flex flex-wrap items-center gap-2">
        {num && <span className="mono text-xs text-[var(--faint)]">Module {num}</span>}
        <AccessBadge access={access} />
        {id && COMING_SOON.has(id) && <SoonBadge />}
      </div>
      <h2 className="mt-1 text-xl font-semibold">{title}</h2>
      <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">{desc}</p>
    </div>
  );
}

export function Notice({ tone = "info", title, children }: { tone?: "info" | "key" | "connect"; title: string; children: React.ReactNode }) {
  const bg = tone === "key" ? "bg-[var(--warn-soft)] border-[var(--warn)]/30" : tone === "connect" ? "bg-[var(--good-soft)] border-[var(--good)]/30" : "bg-[var(--sunken)] border-[var(--line)]";
  return (
    <div className={`mb-5 rounded-xl border px-4 py-3 text-sm ${bg}`}>
      <div className="font-medium">{title}</div>
      <div className="mt-0.5 text-[var(--muted)]">{children}</div>
    </div>
  );
}

export function Stat({ label, value, note, color }: { label: string; value: string; note?: string; color?: string }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mono mt-1 text-2xl font-semibold" style={color ? { color } : undefined}>{value}</div>
      {note && <div className="text-xs text-[var(--faint)]">{note}</div>}
    </div>
  );
}

export function CodeBlock({ label, code }: { label: string; code: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--sunken)]">
      <div className="flex items-center justify-between border-b border-[var(--line)] px-3 py-1.5 text-xs text-[var(--muted)]">
        <span>{label}</span>
        <button className="hover:text-[var(--text)]" onClick={() => { navigator.clipboard?.writeText(code); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="mono max-h-80 overflow-auto p-3 text-xs leading-relaxed">{code}</pre>
    </div>
  );
}

export function Check({ ok, partial }: { ok: boolean; partial?: boolean }) {
  if (partial) return <span className="pill sev-medium">Partial</span>;
  return ok ? <span className="text-[var(--good)]" aria-label="pass">✓</span> : <span className="text-[var(--bad)]" aria-label="fail">✕</span>;
}

export function Sparkline({ values, color = "var(--accent)", w = 120, h = 32 }: { values: number[]; color?: string; w?: number; h?: number }) {
  const max = Math.max(...values), min = Math.min(...values);
  const pts = values.map((v, i) => `${Math.round((i / (values.length - 1)) * w)},${Math.round(h - ((v - min) / Math.max(1, max - min)) * (h - 4) - 2)}`);
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <polyline points={pts.join(" ")} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function Table({ head, children, minWidth = 640 }: { head: string[]; children: React.ReactNode; minWidth?: number }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm" style={{ minWidth }}>
        <thead className="border-b border-[var(--line)] text-left text-xs text-[var(--faint)]">
          <tr>{head.map((h, i) => <th key={i} className="px-4 py-2 font-normal">{h}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-[var(--line)]">{children}</tbody>
      </table>
    </div>
  );
}

export const td = "px-4 py-2.5";
