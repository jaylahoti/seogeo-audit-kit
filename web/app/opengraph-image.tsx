import { ImageResponse } from "next/og";

// The preview card shown when the link is shared (LinkedIn, Slack, X).
export const alt = "SEOGEO Audit Kit — SEO and GEO audits for programmatic sites, reported per template";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  const rows = [
    ["/buildings/{slug}", "3,940", 31],
    ["/neighborhoods/{slug}", "310", 55],
    ["/landlords/{slug}", "286", 44],
    ["/blog/{slug}", "64", 81],
  ] as const;
  const color = (v: number) => (v < 50 ? "#f0707a" : v < 70 ? "#e2a33b" : "#4cc38a");
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", background: "#0c0c10", color: "#ececf1", padding: 72, fontFamily: "sans-serif" }}>
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", width: 600 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
            <svg width="64" height="64" viewBox="0 0 32 32">
              <rect width="32" height="32" rx="8" fill="#ececf1" />
              <rect x="7" y="7" width="7.5" height="7.5" rx="2" fill="#0c0c10" />
              <rect x="7" y="17.5" width="7.5" height="7.5" rx="2" fill="#0c0c10" />
              <rect x="17.5" y="17.5" width="7.5" height="7.5" rx="2" fill="#0c0c10" />
              <path d="M21.25 6.4c.35 2.55 1.6 3.8 4.35 4.35-2.75.55-4 1.8-4.35 4.35-.35-2.55-1.6-3.8-4.35-4.35 2.75-.55 4-1.8 4.35-4.35z" fill="#0c0c10" />
            </svg>
            <div style={{ display: "flex", fontSize: 40 }}>
              <span style={{ fontWeight: 700 }}>SEOGEO</span>
              <span style={{ color: "#9a9aa8", marginLeft: 12 }}>Audit Kit</span>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 60, fontWeight: 700, lineHeight: 1.1, letterSpacing: -1 }}>Fix 10,000 pages by fixing 6 templates.</div>
            <div style={{ fontSize: 26, color: "#9a9aa8", marginTop: 24 }}>SEO and GEO audits: rank on Google, get cited by AI. Open source.</div>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", marginLeft: 48, flex: 1 }}>
          <div style={{ display: "flex", flexDirection: "column", border: "2px solid #25252e", borderRadius: 20, background: "#131318", padding: 24 }}>
            <div style={{ display: "flex", fontSize: 18, color: "#6e6e7b", marginBottom: 12 }}>Templates · AI readiness</div>
            {rows.map(([p, n, v]) => (
              <div key={p} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderTop: "1px solid #25252e", fontSize: 20 }}>
                <span style={{ fontFamily: "monospace" }}>{p}</span>
                <span style={{ display: "flex", alignItems: "center", gap: 16 }}>
                  <span style={{ color: "#9a9aa8" }}>{n}</span>
                  <span style={{ color: color(v), fontWeight: 700, width: 40, textAlign: "right" }}>{v}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    ),
    size,
  );
}
