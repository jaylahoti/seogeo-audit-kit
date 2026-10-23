export function scoreColor(v: number) {
  if (v < 50) return "var(--bad)";
  if (v < 70) return "var(--warn)";
  return "var(--good)";
}

export function ScoreBadge({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="text-[11px] text-[var(--faint)]">{label}</div>
      <div className="text-xl font-semibold tabular-nums" style={{ color: scoreColor(value) }}>{value}</div>
    </div>
  );
}

export function ScoreRing({ value, label, size = 88 }: { value: number; label: string; size?: number }) {
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  return (
    <div className="flex items-center gap-3">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${label} ${value} out of 100`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--sunken)" strokeWidth="7" />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke={scoreColor(value)} strokeWidth="7" strokeLinecap="round"
          strokeDasharray={`${(value / 100) * c} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" fontSize={size / 3.6} fontWeight="600" fill="var(--text)">{value}</text>
      </svg>
      <div className="text-sm font-medium">{label}</div>
    </div>
  );
}

export function Bar({ value, max = 100, color }: { value: number; max?: number; color?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--sunken)]">
      <div className="h-full rounded-full" style={{ width: `${Math.min(100, (value / max) * 100)}%`, background: color ?? scoreColor(value) }} />
    </div>
  );
}
