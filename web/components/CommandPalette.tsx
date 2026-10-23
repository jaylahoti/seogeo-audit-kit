"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { MODULES } from "@/lib/modules";
import { AccessBadge } from "@/components/ui";

export function CommandPalette({ go }: { go: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) { setQ(""); setActive(0); setTimeout(() => input.current?.focus(), 0); }
  }, [open]);

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return MODULES.filter((m) => !needle || `${m.label} ${m.group}`.toLowerCase().includes(needle));
  }, [q]);

  function choose(id: string) { setOpen(false); go(id); }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="mb-4 flex w-full items-center justify-between rounded-md border border-[var(--line)] px-2.5 py-1.5 text-sm text-[var(--faint)] hover:border-[var(--line-strong)]"
      >
        <span>Search modules</span>
        <kbd className="mono rounded border border-[var(--line)] px-1 text-[10px]">⌘K</kbd>
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-[15vh]" onMouseDown={() => setOpen(false)}>
          <div
            role="dialog" aria-modal="true" aria-label="Search modules"
            className="card w-full max-w-lg overflow-hidden shadow-2xl"
            onMouseDown={(e) => e.stopPropagation()}
          >
            <input
              ref={input} value={q} placeholder="Jump to a module…" aria-label="Search modules"
              onChange={(e) => { setQ(e.target.value); setActive(0); }}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
                if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
                if (e.key === "Enter" && results[active]) choose(results[active].id);
              }}
              className="w-full border-b border-[var(--line)] bg-transparent px-4 py-3 text-sm outline-none"
            />
            <ul className="max-h-80 overflow-y-auto p-1.5" role="listbox">
              {results.map((m, i) => (
                <li key={m.id} role="option" aria-selected={i === active}>
                  <button
                    onMouseEnter={() => setActive(i)} onClick={() => choose(m.id)}
                    className={`flex w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left text-sm ${i === active ? "bg-[var(--sunken)]" : ""}`}
                  >
                    <span>{m.label} <span className="text-xs text-[var(--faint)]">· {m.group}</span></span>
                    <AccessBadge access={m.access} />
                  </button>
                </li>
              ))}
              {results.length === 0 && <li className="px-3 py-6 text-center text-sm text-[var(--muted)]">No module matches “{q}”.</li>}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}
