"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { getAudit, toAudit } from "@/lib/api";
import { rememberAudit, siteOf } from "@/lib/recent";
import type { Audit } from "@/lib/mock";
import { SAMPLE_AUDIT } from "@/lib/mock";
import { Report } from "@/components/Report";
import { RefreshContext } from "@/components/RefreshContext";

type State = { kind: "loading" } | { kind: "ready"; audit: Audit } | { kind: "running" } | { kind: "missing" } | { kind: "error"; message: string };

export function ReportLoader({ id }: { id: string }) {
  const [state, setState] = useState<State>(id === SAMPLE_AUDIT.id ? { kind: "ready", audit: SAMPLE_AUDIT } : { kind: "loading" });
  const [waking, setWaking] = useState(false);

  const load = useCallback(async () => {
    if (id === SAMPLE_AUDIT.id) return;
    try {
      const a = await getAudit(id, () => setWaking(true));
      if (!a) setState({ kind: "missing" });
      else if (a.status === "error") {
        rememberAudit({ id, site: siteOf(a.input_url), at: a.created_at * 1000, status: "error" });
        setState({ kind: "error", message: a.error ?? "The audit failed." });
      } else if (a.status !== "done") setState({ kind: "running" });
      else {
        rememberAudit({ id, site: siteOf(a.input_url), at: a.created_at * 1000, status: "done", geo: a.result?.geo?.score ?? null });
        setState({ kind: "ready", audit: toAudit(a) });
      }
    } catch (e) {
      setState({ kind: "error", message: e instanceof Error ? e.message : "Couldn't load the audit." });
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  if (state.kind === "ready") {
    return (
      <RefreshContext.Provider value={load}>
        <Report audit={state.audit} />
      </RefreshContext.Provider>
    );
  }
  return (
    <main className="mx-auto max-w-xl px-4 py-24 text-center">
      {state.kind === "loading" && (
        <p className="text-sm text-[var(--muted)]">
          {waking ? "Waking up the audit server. It sleeps when nobody has used it for a while, so this takes up to a minute…" : "Loading report…"}
        </p>
      )}
      {state.kind === "running" && (
        <>
          <h1 className="text-xl font-semibold">This audit is still running</h1>
          <Link href={`/run?id=${encodeURIComponent(id)}`} className="btn mt-4">Watch progress</Link>
        </>
      )}
      {state.kind === "missing" && (
        <>
          <h1 className="text-xl font-semibold">Report not found</h1>
          <p className="mt-2 text-sm text-[var(--muted)]">There&apos;s no report at this link. Check that the link is complete, or run the audit again.</p>
          <Link href="/" className="btn mt-4">Run a new audit</Link>
        </>
      )}
      {state.kind === "error" && (
        <>
          <h1 className="text-xl font-semibold">The audit didn't finish</h1>
          <p className="mt-2 text-sm text-[var(--bad)]">{state.message}</p>
          <Link href="/" className="btn mt-4">Try another URL</Link>
        </>
      )}
    </main>
  );
}
