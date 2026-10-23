"use client";

import { useMemo, useState } from "react";
import type { Audit } from "@/lib/mock";
import { fmt } from "@/lib/mock";

// Categorical colors for clusters (distinct in light and dark).
const COLORS = ["#5b5bd6", "#1f9e89", "#d9822b", "#c2407a", "#3b82c4", "#7a8a2e"];

function rng(seed: number) {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
}

export function MlLab({ audit }: { audit: Audit }) {
  const [hover, setHover] = useState<string | null>(null);

  const points = useMemo(() => {
    const r = rng(7);
    const centers = [[30, 35], [72, 28], [55, 70], [20, 72], [85, 65], [50, 45]];
    return audit.templates.flatMap((t, i) => {
      const n = Math.min(70, Math.max(8, Math.round(Math.log2(t.pages) * 6)));
      return Array.from({ length: n }, () => {
        const a = r() * Math.PI * 2;
        const d = Math.sqrt(r()) * 9;
        // Rounded so server and client render identical attributes.
        const round = (v: number) => Math.round(v * 100) / 100;
        return { id: t.id, x: round(centers[i][0] + Math.cos(a) * d), y: round(centers[i][1] + Math.sin(a) * d), c: COLORS[i] };
      });
    });
  }, [audit]);

  const m = audit.ml;

  return (
    <div className="mt-6 space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Template clustering (ARI)" value={m.ari.toFixed(2)} note={`vs hand labels on ${m.labelledSites} sites`} />
        <Metric label="Cluster purity" value={`${Math.round(m.purity * 100)}%`} note="pages in the right template" />
        <Metric label="Judge vs human (Cohen's κ)" value={m.kappa.toFixed(2)} note="substantial agreement" />
        <Metric label="Judge agreement" value={`${Math.round(m.judgeAgree * 100)}%`} note="on issue severity" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="card p-4">
          <div className="mb-1 text-sm font-medium">Template map</div>
          <p className="text-xs text-[var(--muted)]">
            Each dot is a sampled page, placed by its URL and HTML-structure features (UMAP to 2D). Colors are the clusters HDBSCAN found.
          </p>
          <svg viewBox="0 0 100 100" className="mt-3 aspect-square max-h-[420px] w-full" role="img" aria-label="Scatter plot of sampled pages grouped into template clusters">
            {points.map((p, i) => (
              <circle
                key={i} cx={p.x} cy={p.y} r={hover && hover !== p.id ? 0.7 : 1}
                fill={p.c} opacity={hover && hover !== p.id ? 0.18 : 0.85}
              />
            ))}
          </svg>
        </div>
        <ul className="card divide-y divide-[var(--line)] self-start">
          {audit.templates.map((t, i) => (
            <li key={t.id} onMouseEnter={() => setHover(t.id)} onMouseLeave={() => setHover(null)} className="flex cursor-default items-center gap-2 px-3 py-2.5 text-sm hover:bg-[var(--sunken)]">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: COLORS[i] }} />
              <span className="mono min-w-0 flex-1 truncate">{t.pattern}</span>
              <span className="mono text-xs text-[var(--muted)]">{fmt(t.pages)}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Explain title="How templates are found" body="URL paths become token patterns; HTML becomes tag-path shingles hashed with MinHash. HDBSCAN clusters both, and the results are merged." />
        <Explain title="How sampling works" body="Five pages per template: random, longest, shortest, newest and one outlier — enough to catch template-wide problems at a fraction of the cost." />
        <Explain title="How the judge is checked" body="On the labelled set, the AI judge's severity ratings are compared with human ratings. Disagreements are reviewed before each release." />
      </div>
    </div>
  );
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mono mt-1 text-2xl font-semibold">{value}</div>
      <div className="text-xs text-[var(--faint)]">{note}</div>
    </div>
  );
}

function Explain({ title, body }: { title: string; body: string }) {
  return (
    <div className="sunken p-4">
      <div className="text-sm font-medium">{title}</div>
      <p className="mt-1 text-sm text-[var(--muted)]">{body}</p>
    </div>
  );
}
