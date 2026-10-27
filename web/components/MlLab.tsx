"use client";

import { useMemo, useState } from "react";
import type { Audit } from "@/lib/mock";
import { fmt } from "@/lib/mock";
import { EvalsPanel } from "@/components/EvalsPanel";

// Categorical colors for clusters (distinct in light and dark).
const COLORS = ["#5b5bd6", "#1f9e89", "#d9822b", "#c2407a", "#3b82c4", "#7a8a2e", "#9b59b6", "#c0392b"];

function rng(seed: number) {
  return () => {
    seed = (seed * 1664525 + 1013904223) % 4294967296;
    return seed / 4294967296;
  };
}

export function MlLab({ audit }: { audit: Audit }) {
  return audit.live ? <LiveLab audit={audit} /> : <SampleLab audit={audit} />;
}

function LiveLab({ audit }: { audit: Audit }) {
  const [hover, setHover] = useState<number | null>(null);
  const ml = audit.live!.ml;
  const layouts = useMemo(() => {
    const by = new Map<number, string[]>();
    for (const p of ml.points) by.set(p.layout, [...(by.get(p.layout) ?? []), p.url]);
    return [...by.entries()].sort((a, b) => (a[0] < 0 ? 1 : b[0] < 0 ? -1 : b[1].length - a[1].length));
  }, [ml.points]);
  const color = (layout: number) => (layout < 0 ? "var(--line-strong)" : COLORS[layout % COLORS.length]);
  const path = (u: string) => u.replace(/^https?:\/\/[^/]+/, "") || "/";

  return (
    <div className="mt-6 space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Layouts found" value={String(ml.layouts)} note="HDBSCAN clusters of page structure" />
        <Metric label="Pages clustered" value={String(ml.pages)} note="sampled across every URL pattern" />
        <Metric label="Unclustered pages" value={String(ml.noise)} note="kept with their URL pattern" />
        <Metric label="Templates" value={String(audit.templates.length)} note="after splitting and merging" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="card p-4">
          <div className="mb-1 text-sm font-medium">Template map</div>
          <p className="text-xs text-[var(--muted)]">
            Each dot is a crawled page, placed by t-SNE from its structure distance (tag paths + heading skeleton, MinHash). Colors are HDBSCAN layouts; grey dots didn't join a cluster.
          </p>
          {ml.points.length ? (
            <svg viewBox="-3 -3 106 106" className="mt-3 aspect-square max-h-[420px] w-full" role="img" aria-label="Scatter plot of crawled pages grouped into layout clusters">
              {ml.points.map((p, i) => (
                <circle key={i} cx={p.x} cy={p.y} r={hover !== null && hover !== p.layout ? 0.9 : 1.4}
                  fill={color(p.layout)} opacity={hover !== null && hover !== p.layout ? 0.15 : 0.9}>
                  <title>{path(p.url)}</title>
                </circle>
              ))}
            </svg>
          ) : (
            <p className="mt-6 text-sm text-[var(--muted)]">Too few pages to draw a map.</p>
          )}
        </div>
        <ul className="card max-h-[480px] divide-y divide-[var(--line)] self-start overflow-y-auto">
          {layouts.map(([layout, urls]) => (
            <li key={layout} onMouseEnter={() => setHover(layout)} onMouseLeave={() => setHover(null)} className="cursor-default px-3 py-2.5 text-sm hover:bg-[var(--sunken)]">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: color(layout) }} />
                <span className="flex-1">{layout < 0 ? "Unclustered" : `Layout ${layout + 1}`}</span>
                <span className="mono text-xs text-[var(--muted)]">{urls.length} pages</span>
              </div>
              <div className="mono mt-1 truncate pl-4.5 text-[11px] text-[var(--faint)]">{path(urls[0])}</div>
            </li>
          ))}
        </ul>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Explain title="How templates are found" body="URL paths become patterns ({id}, {slug}). Pages are fingerprinted by shallow tag paths and their heading skeleton, compared with MinHash, and clustered with HDBSCAN. URL patterns hiding two layouts are split; sibling patterns sharing one are merged." />
        <Explain title="How sampling works" body="Sitemaps are sampled fairly across every file family and weighted back up. Each template keeps five representative pages: longest, shortest, newest, most unique, and one more." />
        <Explain title="How it's checked" body="Below: the same pipeline run on generated sites where the right answer is known, scored for page types, rule checks and Claude's reading." />
      </div>
      <EvalsPanel />
    </div>
  );
}

function SampleLab({ audit }: { audit: Audit }) {
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

  return (
    <div className="mt-6 space-y-6">
      <EvalsPanel />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="card p-4">
          <div className="mb-1 text-sm font-medium">Template map</div>
          <p className="text-xs text-[var(--muted)]">
            Each dot is a crawled page, placed by t-SNE from its structure distance (tag paths + heading skeleton, MinHash). Colors are the layouts HDBSCAN found.
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
        <Explain title="How templates are found" body="URL paths become patterns ({id}, {slug}). Pages are fingerprinted by shallow tag paths and their heading skeleton, compared with MinHash, and clustered with HDBSCAN. URL patterns hiding two layouts are split; sibling patterns sharing one are merged." />
        <Explain title="How sampling works" body="Sitemaps are sampled fairly across every file family and weighted back up. Each template keeps five representative pages: longest, shortest, newest, most unique, and one more." />
        <Explain title="How it's checked" body="The scores above come from running the real pipeline on generated sites with known answers. The test suite fails if they drop." />
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
