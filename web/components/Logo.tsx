// Brand mark: a 2×2 grid of tiles (templates) with one tile replaced by a four-point
// spark (AI search). Drawn with currentColor so it follows the light/dark theme.

export function LogoMark({ size = 24, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="8" fill="currentColor" />
      <g fill="var(--logo-ink, #fff)">
        <rect x="7" y="7" width="7.5" height="7.5" rx="2" />
        <rect x="7" y="17.5" width="7.5" height="7.5" rx="2" />
        <rect x="17.5" y="17.5" width="7.5" height="7.5" rx="2" />
        {/* four-point spark in the top-right tile */}
        <path d="M21.25 6.4c.35 2.55 1.6 3.8 4.35 4.35-2.75.55-4 1.8-4.35 4.35-.35-2.55-1.6-3.8-4.35-4.35 2.75-.55 4-1.8 4.35-4.35z" />
      </g>
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <LogoMark size={24} className="text-[var(--text)] [--logo-ink:var(--bg)]" />
      <span className="whitespace-nowrap text-sm tracking-tight">
        <span className="font-semibold">SEOGEO</span>
        <span className="hidden text-[var(--muted)] sm:inline"> Audit Kit</span>
      </span>
    </span>
  );
}

// Static SVG used for the favicon (app/icon.svg) — keep in sync with LogoMark.
export const LOGO_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#16161d"/><g fill="#fff"><rect x="7" y="7" width="7.5" height="7.5" rx="2"/><rect x="7" y="17.5" width="7.5" height="7.5" rx="2"/><rect x="17.5" y="17.5" width="7.5" height="7.5" rx="2"/><path d="M21.25 6.4c.35 2.55 1.6 3.8 4.35 4.35-2.75.55-4 1.8-4.35 4.35-.35-2.55-1.6-3.8-4.35-4.35 2.75-.55 4-1.8 4.35-4.35z"/></g></svg>`;
