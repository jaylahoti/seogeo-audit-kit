import evals from "@/lib/evals.json";

type Agree = { n: number; accuracy: number; kappa: number };
const pct = (v: number) => `${Math.round(v * 100)}%`;

export const EVAL_SUMMARY = `Eval ARI ${evals.page_types.ari.toFixed(2)} · checks F1 ${evals.checks.f1.toFixed(2)}`;

function Row({ label, heur, claude }: { label: string; heur: Agree; claude?: Agree }) {
  return (
    <tr>
      <td className="py-2 pr-3">{label}</td>
      <td className="mono py-2 pr-3">{pct(heur.accuracy)} <span className="text-[var(--faint)]">κ {heur.kappa.toFixed(2)}</span></td>
      <td className="mono py-2">{claude ? <>{pct(claude.accuracy)} <span className="text-[var(--faint)]">κ {claude.kappa.toFixed(2)}</span></> : "—"}</td>
    </tr>
  );
}

/** Scores from api/evals on generated sites with known answers. Re-run with `uv run python -m evals.run --claude`. */
export function EvalsPanel() {
  const { page_types: pt, checks, summaries } = evals;
  const claude = summaries.claude;
  const heur = claude?.heuristic_same_pages ?? summaries.heuristic;
  const misses = Object.entries(checks.per_check).filter(([, v]) => v.fn || v.fp);
  return (
    <div className="card p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold">Evals: how often it&apos;s right</h3>
        <span className="text-xs text-[var(--faint)]">{evals.dataset} · {new Date(evals.generated_at * 1000).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span>
      </div>
      <p className="mt-1 text-xs text-[var(--muted)]">
        Generated sites with known answers: real page types, layouts that hide behind one URL pattern, and bugs planted on purpose.
        The tests fail if these scores drop, so every change is checked against them.
      </p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sunken p-3"><div className="text-xs text-[var(--muted)]">Page types (ARI)</div><div className="mono mt-0.5 text-xl font-semibold">{pt.ari.toFixed(2)}</div><div className="text-[11px] text-[var(--faint)]">URL patterns alone: {pt.ari_url_only.toFixed(2)}</div></div>
        <div className="sunken p-3"><div className="text-xs text-[var(--muted)]">Page-count error</div><div className="mono mt-0.5 text-xl font-semibold">{(pt.count_error * 100).toFixed(1)}%</div><div className="text-[11px] text-[var(--faint)]">estimated vs true pages per type</div></div>
        <div className="sunken p-3"><div className="text-xs text-[var(--muted)]">Rule checks</div><div className="mono mt-0.5 text-xl font-semibold">F1 {checks.f1.toFixed(2)}</div><div className="text-[11px] text-[var(--faint)]">precision {checks.precision.toFixed(2)} · recall {checks.recall.toFixed(2)}</div></div>
        <div className="sunken p-3"><div className="text-xs text-[var(--muted)]">Claude vs truth (κ)</div><div className="mono mt-0.5 text-xl font-semibold">{claude ? claude.verdict.kappa.toFixed(2) : "—"}</div><div className="text-[11px] text-[var(--faint)]">{claude ? `quotable summary · ${claude.calls} pages · $${claude.cost_usd.toFixed(2)}` : "run with --claude"}</div></div>
      </div>
      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[420px] text-sm">
          <thead className="text-left text-xs text-[var(--faint)]"><tr><th className="pb-1 font-normal">Question about each page</th><th className="pb-1 font-normal">Quick heuristic</th><th className="pb-1 font-normal">Claude Haiku</th></tr></thead>
          <tbody className="divide-y divide-[var(--line)]">
            <Row label="Is there a quotable summary sentence?" heur={heur.verdict} claude={claude?.verdict} />
            <Row label="Are the key facts up front?" heur={heur.facts_first} claude={claude?.facts_first} />
          </tbody>
        </table>
      </div>
      <ul className="mt-4 space-y-1 text-xs text-[var(--muted)]">
        <li>• The heuristic treats any sentence with the page&apos;s name and a number as a summary, so “Call the Elm Court office at 555 0100” fools it. That&apos;s why Claude makes the final call.</li>
        <li>• Known miss: two URL sections sharing one layout (like /neighborhood/… and /area/…) are kept as separate page types. Merging is limited to one section on purpose, to avoid joining different page types.</li>
        {misses.map(([id, v]) => <li key={id}>• <span className="mono">{id}</span>: {v.fn ? `missed ${v.fn}× — the bug was on only some pages and none of the samples had it` : `${v.fp} false alarm(s)`}.</li>)}
      </ul>
    </div>
  );
}
