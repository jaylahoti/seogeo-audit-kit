import type { Metadata } from "next";
import Link from "next/link";
import { ThemeToggle, THEME_SCRIPT } from "@/components/ThemeToggle";
import "./globals.css";

export const metadata: Metadata = {
  title: "TemplateScope",
  description: "Open-source SEO and GEO audits for programmatic sites, reported per template.",
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
        <header className="sticky top-0 z-30 border-b border-[var(--line)] bg-[var(--bg)]/85 backdrop-blur">
          <div className="mx-auto flex h-14 max-w-[1280px] items-center justify-between gap-4 px-4">
            <Link href="/" className="flex items-center gap-2 text-sm font-semibold">
              <span className="grid h-6 w-6 place-items-center rounded-md bg-[var(--text)] text-[11px] text-[var(--bg)]">TS</span>
              TemplateScope
            </Link>
            <nav className="flex items-center gap-4 text-sm text-[var(--muted)] sm:gap-5">
              <Link href="/#modules" className="hidden hover:text-[var(--text)] sm:inline">Modules</Link>
              <Link href="/#samples" className="hover:text-[var(--text)]">Samples</Link>
              <a href="https://github.com/jaylahoti" target="_blank" rel="noreferrer" className="hover:text-[var(--text)]">GitHub</a>
              <ThemeToggle />
            </nav>
          </div>
        </header>
        <div className="flex-1">{children}</div>
        <footer className="border-t border-[var(--line)]">
          <div className="mx-auto flex max-w-[1280px] flex-wrap items-center justify-between gap-3 px-4 py-6 text-xs text-[var(--faint)]">
            <span>TemplateScope · open source, MIT license</span>
            <span>Built by Jay Lahoti</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
