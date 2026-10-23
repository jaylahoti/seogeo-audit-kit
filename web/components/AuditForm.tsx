"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createAudit } from "@/lib/api";

export function AuditForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    let value = url.trim();
    if (value && !/^https?:\/\//i.test(value)) value = `https://${value}`; // allow "example.com"
    try {
      const u = new URL(value);
      if (!/^https?:$/.test(u.protocol) || !u.hostname.includes(".")) throw new Error();
    } catch {
      setErr("Enter a website or sitemap URL, like example.com or https://example.com/sitemap.xml");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const { id } = await createAudit(value);
      router.push(`/run?id=${encodeURIComponent(id)}&url=${encodeURIComponent(value)}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't start the audit.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="text-left">
      <div className="card flex items-center gap-2 p-1.5 shadow-sm">
        <span className="pl-2 text-[var(--faint)]" aria-hidden>⌕</span>
        <input
          value={url}
          onChange={(e) => { setUrl(e.target.value); setErr(""); }}
          placeholder="yoursite.com or yoursite.com/sitemap.xml"
          aria-label="Website or sitemap URL"
          className="mono h-10 min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        <button className="btn btn-primary h-10 px-4" disabled={busy}>{busy ? "Starting…" : "Run audit"}</button>
      </div>
      {err && <p className="mt-2 text-sm text-[var(--bad)]">{err}</p>}
      <a href="/report/demo-nestlist" className="mt-2 inline-block text-xs text-[var(--muted)] underline-offset-2 hover:underline">
        Or open a sample report
      </a>
    </form>
  );
}
