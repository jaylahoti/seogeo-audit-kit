"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function AuditForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [err, setErr] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const u = new URL(url.trim());
      if (!/^https?:$/.test(u.protocol)) throw new Error();
    } catch {
      setErr("Enter a full sitemap URL, starting with https://");
      return;
    }
    // UI prototype: every run plays the sample audit.
    router.push(`/run?url=${encodeURIComponent(url.trim())}`);
  }

  return (
    <form onSubmit={submit} className="text-left">
      <div className="card flex items-center gap-2 p-1.5 shadow-sm">
        <span className="pl-2 text-[var(--faint)]" aria-hidden>⌕</span>
        <input
          value={url}
          onChange={(e) => { setUrl(e.target.value); setErr(""); }}
          placeholder="https://yoursite.com/sitemap.xml"
          aria-label="Sitemap URL"
          className="mono h-10 min-w-0 flex-1 bg-transparent text-sm outline-none"
        />
        <button className="btn btn-primary h-10 px-4">Run audit</button>
      </div>
      {err && <p className="mt-2 text-sm text-[var(--bad)]">{err}</p>}
      <button
        type="button"
        onClick={() => setUrl("https://nestlist.example/sitemap.xml")}
        className="mt-2 text-xs text-[var(--muted)] underline-offset-2 hover:underline"
      >
        Try an example sitemap
      </button>
    </form>
  );
}
