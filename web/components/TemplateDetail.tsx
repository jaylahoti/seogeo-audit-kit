"use client";

import { useState } from "react";
import type { ClaudeEvidence, Finding, Template } from "@/lib/mock";
import { fmt } from "@/lib/mock";

const TABS = [
  ["ai", "AI readiness"],
  ["seo", "SEO"],
  ["samples", "Sample pages"],
] as const;

const METHOD_LABEL: Record<string, string> = {
  rule: "Rule check",
  heuristic: "Heuristic · Claude confirms next",
  render: "Headless browser",
  psi: "PageSpeed Insights",
  crawl: "Crawl from home page",
  claude: "Claude",
};

export function TemplateDetail({ t }: { t: Template }) {
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("ai");
  const findings = t.findings.filter((f) => f.area === tab);
  const hasFacts = t.samples.some((s) => s.factsTotal != null);
  const hasLcp = t.samples.some((s) => s.lcp != null);

  return (
    <div className="border-t border-[var(--line)] bg-[var(--panel)] px-4 pb-5 pt-2 md:px-8">
      <div role="tablist" className="flex gap-5 border-b border-[var(--line)]">
        {TABS.map(([k, label]) => (
          <button key={k} role="tab" aria-selected={tab === k} className="tab" onClick={() => setTab(k)}>
            {label}
            <span className="ml-1.5 text-[var(--faint)]">{k === "samples" ? t.samples.length : t.findings.filter((f) => f.area === k).length}</span>
          </button>
        ))}
      </div>

      {tab === "ai" && (
        <div className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <FindingList findings={findings} evidence={t.evidence} />
          <div className="space-y-3">
            {t.citation ? (
              <div className="sunken p-3">
                <div className="text-xs text-[var(--muted)]">AI citation check</div>
                <div className="mt-1 text-sm">Cited in <b>{t.citation.cited}</b> of {t.citation.asked} answers</div>
                {t.citation.citedInstead.length > 0 && (
                  <div className="mt-2 text-xs text-[var(--muted)]">
                    Cited instead: {t.citation.citedInstead.map((d) => <span key={d} className="mono mr-1.5 text-[var(--text)]">{d}</span>)}
                  </div>
                )}
              </div>
            ) : (
              <Pending title="AI citation check" text="Claude asks this template's questions with web search and records who gets cited. Arrives with the Claude checks." />
            )}
            {t.questions && t.questions.length > 0 && (
              <div className="sunken p-3">
                <div className="text-xs text-[var(--muted)]">Questions this template should answer</div>
                <ul className="mt-1.5 space-y-1 text-sm">{t.questions.map((q) => <li key={q}>“{q}”</li>)}</ul>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "seo" && (
        <div className="mt-4 grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <FindingList findings={findings} evidence={t.evidence} />
          <div className="space-y-3">
            {t.cwv ? (
              <div className="sunken p-3">
                <div className="text-xs text-[var(--muted)]">Core Web Vitals · mobile{t.cwv.source ? ` · ${t.cwv.source.startsWith("field") ? "real users" : "lab"}` : ", p75"}</div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                  <Vital label="LCP" value={t.cwv.lcp != null ? `${t.cwv.lcp.toFixed(1)}s` : "—"} ok={t.cwv.lcp == null || t.cwv.lcp <= 2.5} />
                  <Vital label="CLS" value={t.cwv.cls != null ? t.cwv.cls.toFixed(2) : "—"} ok={t.cwv.cls == null || t.cwv.cls <= 0.1} />
                  <Vital label="INP" value={t.cwv.inp != null ? `${Math.round(t.cwv.inp)}ms` : "—"} ok={t.cwv.inp == null || t.cwv.inp <= 200} />
                </div>
              </div>
            ) : (
              <Pending title="Core Web Vitals" text="Not measured for this template. Add a free PSI_API_KEY to the API to measure the largest templates." />
            )}
            {t.notIndexedReasons ? (
              <div className="sunken p-3">
                <div className="text-xs text-[var(--muted)]">Why pages aren't indexed (Search Console)</div>
                <ul className="mt-2 space-y-1.5 text-sm">
                  {t.notIndexedReasons.map((r) => (
                    <li key={r.reason} className="flex justify-between gap-2"><span className="truncate">{r.reason}</span><span className="mono text-xs">{Math.round(r.share * 100)}%</span></li>
                  ))}
                  {t.notIndexedReasons.length === 0 && <li className="text-[var(--muted)]">All submitted pages indexed.</li>}
                </ul>
              </div>
            ) : (
              <Pending title="Indexation" text="Connect Google Search Console to see indexed vs submitted pages and why pages aren't indexed." />
            )}
            {t.passed && t.passed.length > 0 && (
              <div className="sunken p-3">
                <div className="text-xs text-[var(--muted)]">Passed</div>
                <ul className="mt-1.5 space-y-1 text-xs text-[var(--good)]">{t.passed.map((p) => <li key={p}>✓ {p}</li>)}</ul>
              </div>
            )}
          </div>
        </div>
      )}

      {tab === "samples" && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-[620px] text-sm">
            <thead className="text-left text-xs text-[var(--faint)]">
              <tr>
                <th className="py-2 font-normal">URL</th><th className="font-normal">Status</th><th className="font-normal">Words</th>
                <th className="font-normal">Schema</th>
                {hasFacts && <th className="font-normal">Facts found</th>}
                {hasLcp ? <th className="font-normal">LCP</th> : <th className="font-normal">Response</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--line)]">
              {t.samples.map((s) => (
                <tr key={s.url}>
                  <td className="max-w-[300px] py-2 pr-4">
                    <a href={s.url} target="_blank" rel="noreferrer" className="mono block truncate hover:underline">{s.url.replace(/^https?:\/\/[^/]+/, "")}</a>
                    {s.title && <div className="truncate text-xs text-[var(--faint)]">{s.title}</div>}
                  </td>
                  <td><span className={`pill ${s.status === 200 ? "sev-low" : "sev-medium"}`}>{s.status}</span></td>
                  <td className="mono">{s.words ? fmt(s.words) : "—"}</td>
                  <td className="max-w-[220px] text-xs">{s.schema.length ? s.schema.join(", ") : <span className="text-[var(--bad)]">none</span>}</td>
                  {hasFacts && <td className="mono">{s.factsFound}/{s.factsTotal}</td>}
                  {hasLcp ? <td className="mono">{s.lcp ? `${s.lcp}s` : "—"}</td> : <td className="mono text-xs">{s.ms != null ? `${s.ms} ms` : "—"}</td>}
                </tr>
              ))}
            </tbody>
          </table>
          {hasFacts && <p className="mt-3 text-xs text-[var(--faint)]">“Facts found”: how many key facts Claude correctly extracted from the page, checked against the page's own data.</p>}
        </div>
      )}
    </div>
  );
}

function Pending({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-[10px] border border-dashed border-[var(--line-strong)] p-3">
      <div className="text-xs text-[var(--muted)]">{title}</div>
      <p className="mt-1 text-xs text-[var(--faint)]">{text}</p>
    </div>
  );
}

function FindingList({ findings, evidence }: { findings: Finding[]; evidence?: ClaudeEvidence[] }) {
  if (!findings.length) return <p className="py-4 text-sm text-[var(--muted)]">No issues found here.</p>;
  return (
    <ul className="space-y-3">
      {findings.map((f) => <FindingCard key={(f.id ?? "") + f.title} f={f} evidence={f.method === "claude" ? evidence : undefined} />)}
    </ul>
  );
}

function FindingCard({ f, evidence }: { f: Finding; evidence?: ClaudeEvidence[] }) {
  const [show, setShow] = useState(f.severity === "high");
  const [why, setWhy] = useState(false);
  const [copied, setCopied] = useState(false);
  return (
    <li className="rounded-lg border border-[var(--line)] p-3">
      <div className="flex items-start gap-3">
        <span className={`pill sev-${f.severity} mt-0.5 capitalize`}>{f.severity}</span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium">{f.title}</div>
          <p className="mt-0.5 text-sm text-[var(--muted)]">{f.detail}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            <span className="mono text-[var(--muted)]">Fix covers ~{fmt(f.pages)} pages</span>
            {f.sampled != null && f.sampled > 1 && <span className="text-[var(--faint)]">{f.affected} of {f.sampled} samples</span>}
            {f.method && <span className="text-[var(--faint)]">{METHOD_LABEL[f.method] ?? f.method}</span>}
            {evidence && evidence.length > 0 && (
              <button className="text-[var(--accent)] hover:underline" onClick={() => setWhy(!why)} aria-expanded={why}>
                {why ? "Hide why" : "Why?"}
              </button>
            )}
            {f.fix && (
              <button className="text-[var(--accent)] hover:underline" onClick={() => setShow(!show)}>
                {show ? "Hide fix" : `Show fix · ${f.fix.label}`}
              </button>
            )}
          </div>
          {f.examples && f.examples.length > 0 && (
            <div className="mt-1.5 space-y-0.5">
              {f.examples.slice(0, 2).map((u) => (
                <a key={u} href={u} target="_blank" rel="noreferrer" className="mono block truncate text-[11px] text-[var(--faint)] hover:text-[var(--text)]">{u}</a>
              ))}
            </div>
          )}
        </div>
      </div>
      {why && evidence && <WhyPanel f={f} evidence={evidence} />}
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

const ANSWERED = { yes: "low", partial: "medium", no: "high" } as const;

/** Shows, per sample page, what Claude read, what it answered, and whether its answer passed the guardrail. */
function WhyPanel({ f, evidence }: { f: Finding; evidence: ClaudeEvidence[] }) {
  const [i, setI] = useState(0);
  const e = evidence[Math.min(i, evidence.length - 1)];
  const a = e.answer;
  const focus = f.id ?? "";
  return (
    <div className="mt-3 rounded-md border border-[var(--line)] bg-[var(--sunken)] text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--line)] px-3 py-2">
        <span className="text-[var(--muted)]">Claude Haiku read {evidence.length} sample page{evidence.length === 1 ? "" : "s"} of this type. This finding sums up their answers.</span>
        {evidence.length > 1 && (
          <div className="flex gap-1">
            {evidence.map((_, n) => (
              <button key={n} onClick={() => setI(n)} className={`mono h-6 w-6 rounded ${n === i ? "bg-[var(--panel)] text-[var(--text)]" : "text-[var(--faint)] hover:text-[var(--text)]"}`}>{n + 1}</button>
            ))}
          </div>
        )}
      </div>
      <div className="grid gap-px bg-[var(--line)] md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="min-w-0 bg-[var(--sunken)] p-3">
          <div className="mb-1.5 font-medium text-[var(--muted)]">What Claude was shown</div>
          <a href={e.url} target="_blank" rel="noreferrer" className="mono block truncate text-[var(--faint)] hover:text-[var(--text)]">{e.url}</a>
          <div className="mt-1.5"><span className="text-[var(--faint)]">Title</span> {e.shown.title ?? "—"}</div>
          <div className="mt-1 text-[var(--faint)]">
            {fmt(e.shown.words)} words of visible text · JSON-LD: {e.shown.jsonld_types.length ? e.shown.jsonld_types.join(", ") : "none"}
          </div>
          <p className="mt-2 line-clamp-6 whitespace-pre-line break-words text-[var(--muted)]">{e.shown.excerpt}{e.shown.excerpt.length >= 500 ? "…" : ""}</p>
        </div>
        <div className="min-w-0 bg-[var(--sunken)] p-3">
          <div className="mb-1.5 font-medium text-[var(--muted)]">What Claude answered <span className="font-normal text-[var(--faint)]">· “{a.page_type}”</span></div>
          {(focus.startsWith("facts") || !focus) && (
            <div className="overflow-x-auto"><table className="w-full">
              <thead><tr className="text-left text-[var(--faint)]"><th className="font-normal">Key fact</th><th className="font-normal">On page</th><th className="font-normal">In text</th><th className="font-normal">In JSON-LD</th></tr></thead>
              <tbody>
                {a.facts.map((x) => (
                  <tr key={x.name} className="align-top">
                    <td className="py-0.5 pr-2">{x.name}</td>
                    <td className="mono max-w-[140px] truncate py-0.5 pr-2 text-[var(--muted)]" title={x.value ?? ""}>{x.value ?? "—"}</td>
                    <td className="py-0.5" style={{ color: x.in_text ? "var(--good)" : "var(--bad)" }}>{x.in_text ? "yes" : "no"}</td>
                    <td className="py-0.5" style={{ color: x.in_structured_data ? "var(--good)" : "var(--bad)" }}>{x.in_structured_data ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
          {focus === "facts_buried" && <p className="mt-2">Key facts in the first ~100 words: <b>{a.facts_up_front ? "yes" : "no"}</b></p>}
          {focus === "no_verdict" && (
            <p>Quotable summary sentence: {a.verdict_sentence ? <q className="italic">{a.verdict_sentence}</q> : <b>none found</b>}</p>
          )}
          {focus === "title_intent" && (
            <p>Title fits how people search: <b>{a.title_matches_intent ? "yes" : "no"}</b>{a.better_title_template && <> · suggested <span className="mono">{a.better_title_template}</span></>}</p>
          )}
          {a.questions.length > 0 && (
            <ul className="mt-2 space-y-1">
              {a.questions.map((q) => (
                <li key={q.question} className="flex items-start gap-2"><span className={`pill sev-${ANSWERED[q.answered]} shrink-0`}>{q.answered}</span><span>{q.question}</span></li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="border-t border-[var(--line)] px-3 py-2 text-[var(--muted)]">
        <span className="font-medium">Guardrail · </span>
        {e.guardrail
          ? e.guardrail.passed
            ? <>Claude quoted <q className="italic">{e.guardrail.quote.slice(0, 140)}{e.guardrail.quote.length > 140 ? "…" : ""}</q> and the quote was found on the page, so it was kept.</>
            : <span style={{ color: "var(--bad)" }}>Claude quoted <q className="italic">{e.guardrail.quote.slice(0, 140)}</q> but that text isn’t on the page, so the quote was thrown away.</span>
          : "No quote to check on this page. Answers are structured output (a fixed schema), so a malformed reply is rejected, not guessed at."}
      </div>
    </div>
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
