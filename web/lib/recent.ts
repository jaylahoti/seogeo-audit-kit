// "Your recent audits": remembered in this browser only (no accounts). Reports themselves are
// saved on the server and open from their link on any device; this is just the visitor's list.

export type RecentAudit = { id: string; site: string; at: number; geo?: number | null; status?: "running" | "done" | "error" };

const KEY = "seogeo.recent";
const MAX = 10;
const EVENT = "seogeo:recent";

export function readRecent(): RecentAudit[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? (JSON.parse(raw) as RecentAudit[]) : [];
    return Array.isArray(list) ? list.filter((r) => r && typeof r.id === "string") : [];
  } catch {
    return []; // storage blocked (private window etc.): no list, everything else still works
  }
}

export function rememberAudit(entry: RecentAudit): void {
  try {
    const list = readRecent().filter((r) => r.id !== entry.id);
    const prev = readRecent().find((r) => r.id === entry.id);
    list.unshift({ ...prev, ...entry, at: prev?.at ?? entry.at });
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX)));
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* ignore */
  }
}

export function forgetAudit(id: string): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(readRecent().filter((r) => r.id !== id)));
    window.dispatchEvent(new Event(EVENT));
  } catch {
    /* ignore */
  }
}

export function onRecentChange(cb: () => void): () => void {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb); // other tabs
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export function siteOf(url: string): string {
  try {
    return new URL(url.includes("://") ? url : `https://${url}`).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
