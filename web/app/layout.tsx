import type { Metadata } from "next";
import Link from "next/link";
import { ThemeToggle, THEME_SCRIPT } from "@/components/ThemeToggle";
import { Wordmark } from "@/components/Logo";
import { NewAuditButton } from "@/components/NewAudit";
import "./globals.css";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3001";
const DESCRIPTION = "Open-source SEO and GEO (AI search) audits for programmatic sites, reported per template.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "SEOGEO Audit Kit — Get found on Google. Get quoted by AI.", template: "%s · SEOGEO Audit Kit" },
  description: DESCRIPTION,
  applicationName: "SEOGEO Audit Kit",
  authors: [{ name: "Jay Lahoti", url: "https://github.com/jaylahoti" }],
  openGraph: { type: "website", siteName: "SEOGEO Audit Kit", title: "SEOGEO Audit Kit", description: DESCRIPTION },
  twitter: { card: "summary_large_image", title: "SEOGEO Audit Kit", description: DESCRIPTION },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="flex min-h-screen flex-col antialiased">
        <header className="sticky top-0 z-30 border-b print:hidden border-[var(--line)] bg-[var(--bg)]/85 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-[1280px] items-center justify-between gap-4 px-4">
            <Link href="/" aria-label="SEOGEO Audit Kit home">
              <Wordmark />
            </Link>
            <nav className="flex items-center gap-4 text-sm text-[var(--muted)] sm:gap-5">
              <Link href="/#modules" className="hidden hover:text-[var(--text)] sm:inline">Modules</Link>
              <Link href="/how-it-works" className="hidden hover:text-[var(--text)] sm:inline">How it works</Link>
              <Link href="/#samples" className="hover:text-[var(--text)]">Samples</Link>
              <a href="https://github.com/jaylahoti/seogeo-audit-kit" target="_blank" rel="noreferrer" className="hidden hover:text-[var(--text)] sm:inline">GitHub</a>
              <NewAuditButton />
              <ThemeToggle />
            </nav>
          </div>
        </header>
        <div className="flex-1">{children}</div>
        <footer className="border-t border-[var(--line)] print:hidden">
          <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-[var(--faint)]">
            <span className="flex items-center gap-2"><Wordmark className="opacity-80" /><span>· <a href="https://github.com/jaylahoti/seogeo-audit-kit" target="_blank" rel="noreferrer" className="underline-offset-2 hover:text-[var(--text)] hover:underline">open source, MIT</a></span></span>
            <span className="flex gap-4"><Link href="/how-it-works" className="hover:text-[var(--text)]">How it works</Link><span>Built by <a href="https://github.com/jaylahoti" target="_blank" rel="noreferrer" className="underline-offset-2 hover:text-[var(--text)] hover:underline">Jay Lahoti</a></span></span>
          </div>
        </footer>
      </body>
    </html>
  );
}
