"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createAudit } from "@/lib/api";
import { RecentAuditsList } from "@/components/RecentAudits";

function normalize(raw: string): string | null {
  let value = raw.trim();
  if (value && !/^https?:\/\//i.test(value)) value = `https://${value}`;
  try {
    const u = new URL(value);
    return /^https?:$/.test(u.protocol) && u.hostname.includes(".") ? value : null;
  } catch {
    return null;
  }
}

async function start(router: ReturnType<typeof useRouter>, url: string, onWaking?: () => void) {
  const { id } = await createAudit(url, onWaking);
  router.push(`/run?id=${encodeURIComponent(id)}&url=${encodeURIComponent(url)}`);
}

/** Re-runs a live report's audit on the same URL. */
export function RerunButton({ url }: { url: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [waking, setWaking] = useState(false);
  return (
    <div className="flex flex-col items-end">
      <button
        className="btn btn-primary" disabled={busy}
        onClick={async () => {
          setBusy(true); setErr("");
          try { await start(router, url, () => setWaking(true)); } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't start"); setBusy(false); setWaking(false); }
        }}
      >
        {busy ? (waking ? "Waking server…" : "Starting…") : "Re-run"}
      </button>
      {err && <span className="mt-1 text-xs text-[var(--bad)]">{err}</span>}
    </div>
  );
}

/** Top-bar button: opens a small box to audit another site from any page. */
export function NewAuditButton() {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return;
    setTimeout(() => input.current?.focus(), 0);
    const close = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, [open]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const value = normalize(url);
    if (!value) { setErr("Enter a site like example.com"); return; }
    setBusy(true); setErr("");
    try {
      await start(router, value, () => setErr("Waking up the audit server, up to a minute…"));
      setUrl("");
      setErr("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't start the audit.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div ref={box} className="relative">
      <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="btn h-8 px-2.5 text-[13px]">
        <span aria-hidden>+</span> New audit
      </button>
      {open && (
        <form onSubmit={submit} className="card absolute right-0 top-10 z-40 w-[min(360px,calc(100vw-2rem))] p-3 shadow-xl">
          <label className="text-xs text-[var(--muted)]" htmlFor="new-audit-url">Website or sitemap URL</label>
          <div className="mt-1.5 flex gap-2">
            <input
              id="new-audit-url" ref={input} value={url} placeholder="example.com"
              onChange={(e) => { setUrl(e.target.value); setErr(""); }}
              className="input mono h-9 min-w-0 flex-1 text-sm"
            />
            <button className="btn btn-primary h-9" disabled={busy}>{busy ? "…" : "Run"}</button>
          </div>
          {err && <p className="mt-1.5 text-xs text-[var(--bad)]">{err}</p>}
          <p className="mt-2 text-[11px] text-[var(--faint)]">Takes 2–4 minutes. Your current report stays at its link.</p>
          <RecentAuditsList onPick={() => setOpen(false)} />
        </form>
      )}
    </div>
  );
}
