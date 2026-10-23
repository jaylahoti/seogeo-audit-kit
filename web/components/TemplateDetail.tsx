"use client";

import { useState } from "react";
import type { Finding, Template } from "@/lib/mock";
import { fmt } from "@/lib/mock";

const TABS = [
  ["ai", "AI readiness"],
  ["seo", "SEO"],
  ["samples", "Sample pages"],
] as const;

export function TemplateDetail({ t }: { t: Template }) {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("ai");
  const findings = t.findings.filter((f) => f.area === tab);

  return (
    <div className="border-t border-[var(--line)] bg-[var(--panel)] px-4 pb-5 pt-2 md:px-8">
      <div role="tablist" className="flex gap-5 border-b border-[var(--line)]">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className="tab" onClick={() => setTab(k)}>
            {label}
            {k !== "samples" && <span className="ml-1.5 text-[var(--faint)]">{t.findings.filter((f) => f.area === k).length}</span>}
          </button>
        ))}
      </div>

      {tab === "ai" && (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <FindingList findings={findings} />
          <div className="space-y-3">
            <div className="sunken p-3">
              <div className="text-xs text-[var(--muted)]">AI citation check</div>
              <div className="mt-1 text-sm">
                Cited in <b>{t.citation.cited}</b> of {t.citation.asked} answers
              </div>
              {t.citation.citedInstead.length > 0 && (
                <div className="mt-2 text-xs text-[var(--muted)]">
                  Cited instead: {t.citation.citedInstead.map((d) => <span key={d} className="mono mr-1.5 text-[var(--text)]">{d}</span>)}
                </div>
              )}
            </div>
            {t.questions.length > 0 && (
              <div className="sunken p-3">
                <div className="text-xs text-[var(--muted)]">Questions this template should answer</div>
                <ul className="mt-1.5 space-y-1 text-sm">{t.questions.map((q) => <li key={q}>“{q}”</li>)}</ul>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "seo" && (
        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <FindingList findings={findings} />
          <div className="space-y-3">
            <div className="sunken p-3">
              <div className="text-xs text-[var(--muted)]">Core Web Vitals · mobile, p75</div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                <Vital label="LCP" value={`${t.cwv.lcp}s`} ok={t.cwv.lcp <= 2.5} />
                <Vital label="CLS" value={t.cwv.cls.toFixed(2)} ok={t.cwv.cls <= 0.1} />
                <Vital label="INP" value={`${t.cwv.inp}ms`} ok={t.cwv.inp <= 200} />
              </div>
            </div>
            <div className="sunken p-3">
              <div className="text-xs text-[var(--muted)]">Why pages aren't indexed (Search Console)</div>
              <ul className="mt-2 space-y-1.5 text-sm">
                {t.notIndexedReasons.map((r) => (
                  <li key={r.reason} className="flex justify-between gap-2"><span className="truncate">{r.reason}</span><span className="mono text-xs">{Math.round(r.share * 100)}%</span></li>
                ))}
                {t.notIndexedReasons.length === 0 && <li className="text-[var(--muted)]">All submitted pages indexed.</li>}
              </ul>
            </div>
          </div>
        </div>
      )}

      {tab === "samples" && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[620px] text-sm">
            <thead className="text-left text-xs text-[var(--faint)]">
              <tr><th className="py-2 font-normal">URL</th><th className="font-normal">Status</th><th className="font-normal">Words</th><th className="font-normal">Schema</th><th className="font-normal">Facts found</th><th className="font-normal">LCP</th></tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)]">
              {t.samples.map((s) => (
                <tr key={s.url}>
                  <td className="mono max-w-[260px] truncate py-2 pr-4">{s.url}</td>
                  <td><span className={`pill ${s.status === 200 ? "sev-low" : "sev-medium"}`}>{s.status}</span></td>
                  <td className="mono">{s.words ? fmt(s.words) : "—"}</td>
                  <td className="text-xs">{s.schema.length ? s.schema.join(", ") : <span className="text-[var(--bad)]">none</span>}</td>
                  <td className="mono">{s.factsFound}/{s.factsTotal}</td>
                  <td className="mono">{s.lcp ? `${s.lcp}s` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-[var(--faint)]">“Facts found”: how many key facts Claude correctly extracted from the page, checked against the page's own data.</p>
        </div>
      )}
    </div>
  );
}

function FindingList({ findings }: { findings: Finding[] }) {
  if (!findings.length) return <p className="py-4 text-sm text-[var(--muted)]">No issues found here.</p>;
  return (
    <ul className="space-y-3">
      {findings.map((f) => <FindingCard key={f.title} f={f} />)}
    </ul>
  );
}

function FindingCard({ f }: { f: Finding }) {
  const [show, setShow] = useState(f.severity === "high");
  const [copied, setCopied] = useState(false);
  return (
    <li className="rounded-lg border border-[var(--line)] p-3">
      <div className="flex items-start gap-3">
        <span className={`pill sev-${f.severity} mt-0.5 capitalize`}>{f.severity}</span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">{f.title}</div>
          <p className="mt-0.5 text-sm text-[var(--muted)]">{f.detail}</p>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
            <span className="mono text-[var(--muted)]">Fix covers {fmt(f.pages)} pages</span>
            {f.fix && (
              <button className="text-[var(--accent)] hover:underline" onClick={() => setShow(!show)}>
                {show ? "Hide fix" : `Show fix · ${f.fix.label}`}
              </button>
            )}
          </div>
        </div>
      </div>
      {f.fix && show && (
        <div className="relative mt-3 overflow-hidden rounded-md border border-[var(--line)] bg-[var(--sunken)]">
          <div className="flex items-center justify-between border-b border-[var(--line)] px-3 py-1.5 text-xs text-[var(--muted)]">
            <span>{f.fix.kind === "jsonld" ? "JSON-LD · validated against schema.org" : "HTML block"}</span>
            <button
              className="hover:text-[var(--text)]"
              onClick={() => { navigator.clipboard?.writeText(f.fix!.content); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
          <pre className="mono max-h-72 overflow-auto p-3 text-xs leading-relaxed">{f.fix.content}</pre>
        </div>
      )}
    </li>
  );
}

function Vital({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className="rounded-md bg-[var(--panel)] px-2 py-2">
      <div className="text-[11px] text-[var(--faint)]">{label}</div>
      <div className="mono text-sm font-medium" style={{ color: ok ? "var(--good)" : "var(--bad)" }}>{value}</div>
    </div>
  );
}
