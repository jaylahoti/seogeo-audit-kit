"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { forgetAudit, onRecentChange, readRecent, type RecentAudit } from "@/lib/recent";
import { scoreColor } from "@/components/Score";

function ago(ms: number): string {
  const s = Math.max(0, (Date.now() - ms) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function href(r: RecentAudit) {
  return r.status === "running" ? `/run?id=${encodeURIComponent(r.id)}&url=${encodeURIComponent(r.site)}` : `/report/${encodeURIComponent(r.id)}`;
}

function useRecent() {
  // Read after mount: the list only exists in this browser, so the server can't render it.
  const [list, setList] = useState<RecentAudit[] | null>(null);
  useEffect(() => {
    setList(readRecent());
    return onRecentChange(() => setList(readRecent()));
  }, []);
  return list;
}

function Status({ r }: { r: RecentAudit }) {
  if (r.status === "running") return <span className="pill sev-medium">Running</span>;
  if (r.status === "error") return <span className="pill sev-high">Failed</span>;
  if (r.geo != null) return <span className="mono text-sm font-semibold" style={{ color: scoreColor(r.geo) }}>GEO {r.geo}</span>;
  return <span className="text-xs text-[var(--faint)]">Done</span>;
}

/** Landing-page section; renders nothing until the visitor has run or opened an audit. */
export function RecentAuditsSection() {
  const list = useRecent();
  if (!list || list.length === 0) return null;
  return (
    <section className="mx-auto max-w-[1280px] px-4 pb-4">
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold">Your recent audits</h2>
        <span className="text-xs text-[var(--faint)]">Saved in this browser · reports open from their link on any device</span>
      </div>
      <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {list.map((r) => (
          <li key={r.id} className="card group flex items-center gap-3 p-3 transition hover:border-[var(--line-strong)]">
            <Link href={href(r)} className="flex min-w-0 flex-1 items-center justify-between gap-3">
              <span className="min-w-0">
                <span className="mono block truncate text-sm">{r.site}</span>
                <span className="text-xs text-[var(--faint)]">{ago(r.at)}</span>
              </span>
              <Status r={r} />
            </Link>
            <button
              onClick={() => forgetAudit(r.id)} aria-label={`Remove ${r.site} from this list`}
              className="text-[var(--faint)] opacity-0 transition hover:text-[var(--text)] focus:opacity-100 group-hover:opacity-100"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Compact list for the top-bar New audit box. */
export function RecentAuditsList({ onPick }: { onPick?: () => void }) {
  const list = useRecent();
  if (!list || list.length === 0) return null;
  return (
    <div className="mt-3 border-t border-[var(--line)] pt-2">
      <div className="mb-1 text-[11px] text-[var(--faint)]">Recent</div>
      <ul className="max-h-56 space-y-0.5 overflow-y-auto">
        {list.slice(0, 6).map((r) => (
          <li key={r.id}>
            <Link href={href(r)} onClick={onPick} className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-[var(--sunken)]">
              <span className="mono min-w-0 truncate">{r.site}</span>
              <span className="flex shrink-0 items-center gap-2 text-xs text-[var(--faint)]">{ago(r.at)} <Status r={r} /></span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
