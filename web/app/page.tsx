import Link from "next/link";
import { AuditForm } from "@/components/AuditForm";
import { ScoreBadge, ScoreRing, Bar, scoreColor } from "@/components/Score";
import { AccessBadge, CodeBlock } from "@/components/ui";
import { SAMPLE_AUDIT, SAMPLE_REPORTS, fmt } from "@/lib/mock";
import { GH_ACTION, MODULES, type Access } from "@/lib/modules";

const MODULE_BLURB: Record<string, string> = {
  technical: "Titles, canonicals, duplicates, orphans and sitemap health, per template.",
  cwv: "LCP, CLS and INP for each template, from Chrome field data or lab runs.",
  ai: "JSON-LD, freshness, a quotable verdict sentence, and whether Claude can pull the facts out.",
  whatai: "The page with and without JavaScript — what GPTBot and ClaudeBot actually see.",
  fixes: "Ready-to-paste JSON-LD, titles, verdict blocks, llms.txt and robots.txt.",
  gsc: "Indexed vs submitted and clicks for each template, plus why pages aren't indexed.",
  bing: "Bing indexation per template — ChatGPT search relies on Bing's index.",
  traffic: "Visits from ChatGPT, Perplexity, Gemini and Claude, by template.",
  visibility: "Your question set, asked on a schedule: cited or not, position, who's cited instead.",
  crawlers: "From your logs: which AI bots crawl which templates, and what errors they hit.",
  monitoring: "Scheduled re-audits and alerts when a deploy breaks a template.",
  gaps: "Questions people ask, mapped to the template that should answer them.",
  ci: "Fail a PR when a template regresses. Run audits from Claude Code or Cursor.",
};

const REPLACES = [
  ["Site crawler", "Screaming Frog, Sitebulb"],
  ["Search data", "Search Console, Bing Webmaster"],
  ["GEO checker", "Page-by-page AI readiness tools"],
  ["AI visibility tracker", "Profound, Peec, Otterly"],
];

const STEPS = [
  ["Read the sitemap", "Up to 5,000 URLs, sampled fairly across every sitemap file. robots.txt respected."],
  ["Find the templates", "URL patterns plus page structure, clustered with HDBSCAN."],
  ["Check a sample", "Rule checks, Core Web Vitals, and Claude reading 5 pages per template."],
  ["Rank the fixes", "By pages covered × severity, each with the code to fix it."],
];

const RUNS_WHERE: { access: Access; text: string }[] = [
  { access: "free", text: "Crawling, technical SEO, Core Web Vitals, what AI sees, AI crawler logs, monitoring, CI." },
  { access: "claude", text: "Fact extraction, judging and fixes, question gaps, Claude citation tracking. About $0.11 per audit." },
  { access: "connect", text: "Your Google Search Console, Bing Webmaster, and GA4 or PostHog. Read-only." },
  { access: "key", text: "ChatGPT, Perplexity, Gemini and Copilot citation tracking, when you self-host." },
];

const FAQ = [
  ["Why per template?", "A programmatic site has thousands of pages but only a handful of templates. Fix the template and every page built from it is fixed — so that's the unit worth reporting on."],
  ["What does an audit cost?", "About $0.11 in Claude usage, paid by the hosted demo. Rules and ML run first for free; Claude only reads 30 sample pages."],
  ["Which parts need my own keys?", "Tracking ChatGPT, Perplexity, Gemini and Copilot citations. Everything else runs on Claude or free Google and Bing APIs."],
  ["Is my site safe to point this at?", "It only fetches public pages, identifies itself as SEOGEOAuditKitBot, respects robots.txt and Crawl-delay, and caps requests per host."],
];

function HeroPreview() {
  const a = SAMPLE_AUDIT;
  return (
    <div className="card overflow-hidden shadow-xl" aria-label="Preview of a SEOGEO Audit Kit report" role="img">
      <div className="flex items-center gap-1.5 border-b border-[var(--line)] px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[var(--line-strong)]" /><span className="h-2.5 w-2.5 rounded-full bg-[var(--line-strong)]" /><span className="h-2.5 w-2.5 rounded-full bg-[var(--line-strong)]" />
        <span className="mono ml-2 truncate text-[11px] text-[var(--faint)]">seogeo-audit-kit.dev/report/{a.site}</span>
      </div>
      <div className="grid grid-cols-[120px_minmax(0,1fr)] text-left">
        <div className="hidden space-y-1 border-r border-[var(--line)] p-3 text-[11px] text-[var(--muted)] sm:block">
          {["Overview", "Technical SEO", "AI readiness", "What AI sees", "Search Console", "AI visibility", "AI crawlers"].map((l, i) => (
            <div key={l} className={`rounded px-1.5 py-1 ${i === 0 ? "bg-[var(--sunken)] font-medium text-[var(--text)]" : ""}`}>{l}</div>
          ))}
        </div>
        <div className="col-span-2 space-y-3 p-4 sm:col-span-1">
          <div className="flex flex-wrap gap-4">
            <ScoreRing value={a.scores.seo} label="SEO" size={56} />
            <ScoreRing value={a.scores.ai} label="AI readiness" size={56} />
            <div className="text-xs"><div className="text-[var(--faint)]">Audit cost</div><div className="mono text-lg font-semibold">${a.cost.toFixed(2)}</div></div>
          </div>
          <div className="divide-y divide-[var(--line)] rounded-lg border border-[var(--line)]">
            {a.templates.slice(0, 4).map((t) => (
              <div key={t.id} className="grid grid-cols-[minmax(0,1fr)_56px_64px] items-center gap-3 px-3 py-2 text-xs">
                <span className="mono truncate">{t.pattern}</span>
                <span className="mono text-right text-[var(--muted)]">{fmt(t.pages)}</span>
                <span className="flex items-center gap-1.5"><span className="mono w-5" style={{ color: scoreColor(t.ai) }}>{t.ai}</span><Bar value={t.ai} /></span>
              </div>
            ))}
          </div>
          <div className="flex items-start gap-2 rounded-lg bg-[var(--bad-soft)] px-3 py-2 text-xs text-[var(--bad)]">
            <span className="font-medium">High</span><span>No JSON-LD on /buildings/{"{slug}"} — one fix covers 3,940 pages</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const groups = ["Audit", "Connect", "Track"] as const;
  return (
    <main>
      {/* Hero */}
      <section className="mx-auto grid max-w-[1280px] items-center gap-12 px-4 pb-16 pt-16 lg:grid-cols-[minmax(0,1fr)_560px] lg:pt-24">
        <div>
          <div className="flex flex-wrap gap-2">
            <span className="pill bg-[var(--accent-soft)] text-[var(--accent)]">SEO + GEO site auditor</span>
            <span className="pill sev-low">Open source · MIT</span>
          </div>
          <h1 className="mt-5 text-4xl font-semibold leading-[1.1] tracking-tight md:text-5xl">
            Fix 10,000 pages by fixing 6 templates.
          </h1>
          <p className="mt-5 max-w-xl text-lg text-[var(--muted)]">
            SEO and GEO audits for programmatic sites: rank on Google and get cited by ChatGPT, Perplexity and Claude — reported per template, so every fix shows how many pages it covers.
          </p>
          <div className="mt-8 max-w-xl"><AuditForm /></div>
          <p className="mt-3 text-xs text-[var(--faint)]">3 free audits a day · about $0.11 each, paid by us · no sign-up</p>
        </div>
        <HeroPreview />
      </section>

      {/* Replaces */}
      <section className="border-y border-[var(--line)] bg-[var(--sunken)]">
        <div className="mx-auto max-w-[1280px] px-4 py-10">
          <p className="mb-5 text-center text-sm text-[var(--muted)]">One report instead of four tools</p>
          <div className="grid gap-px overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--line)] sm:grid-cols-2 lg:grid-cols-4">
            {REPLACES.map(([k, v]) => (
              <div key={k} className="bg-[var(--panel)] p-4">
                <div className="text-sm font-medium">{k}</div>
                <div className="mt-0.5 text-xs text-[var(--faint)]">{v}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Modules */}
      <section id="modules" className="mx-auto max-w-[1280px] scroll-mt-20 px-4 py-20">
        <div className="mb-10 max-w-2xl">
          <h2 className="text-3xl font-semibold tracking-tight">13 modules, one report</h2>
          <p className="mt-2 text-[var(--muted)]">Audit runs on every scan. Connect adds your own search and analytics data. Track runs on a schedule and catches regressions.</p>
        </div>
        <div className="space-y-10">
          {groups.map((g) => (
            <div key={g}>
              <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-[var(--faint)]">{g}</h3>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {MODULES.filter((m) => m.group === g && m.num).map((m) => (
                  <Link key={m.id} href={`/report/demo-nestlist?m=${m.id}`} className="card group p-4 transition hover:border-[var(--line-strong)]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium">{m.label}</span>
                      <AccessBadge access={m.access} />
                    </div>
                    <p className="mt-1.5 text-sm text-[var(--muted)]">{MODULE_BLURB[m.id]}</p>
                    <span className="mt-3 inline-block text-xs text-[var(--faint)] transition group-hover:text-[var(--text)]">See it in the sample report →</span>
                  </Link>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-[var(--line)]">
        <div className="mx-auto max-w-[1280px] px-4 py-20">
          <h2 className="mb-8 text-3xl font-semibold tracking-tight">How an audit works</h2>
          <ol className="grid gap-px overflow-hidden rounded-xl border border-[var(--line)] bg-[var(--line)] md:grid-cols-4">
            {STEPS.map(([t, d], i) => (
              <li key={t} className="bg-[var(--panel)] p-5">
                <span className="mono text-xs text-[var(--faint)]">0{i + 1}</span>
                <h3 className="mt-2 text-sm font-semibold">{t}</h3>
                <p className="mt-1 text-sm text-[var(--muted)]">{d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* What's free */}
      <section className="border-t border-[var(--line)] bg-[var(--sunken)]">
        <div className="mx-auto grid max-w-[1280px] gap-10 px-4 py-20 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight">What runs where</h2>
            <p className="mt-2 text-[var(--muted)]">The hosted demo runs on Claude and free APIs. Everything else is built and open source — self-host it and add your own keys.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {RUNS_WHERE.map(({ access, text }) => (
              <div key={access} className="card p-4">
                <AccessBadge access={access} />
                <p className="mt-2 text-sm text-[var(--muted)]">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Samples */}
      <section id="samples" className="mx-auto max-w-[1280px] scroll-mt-20 px-4 py-20">
        <h2 className="text-3xl font-semibold tracking-tight">Sample reports</h2>
        <p className="mb-6 mt-2 text-[var(--muted)]">Pre-run audits of example sites — open one to explore every module.</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {SAMPLE_REPORTS.map((r) => (
            <Link key={r.site} href={`/report/${r.id}`} className="card group p-4 transition hover:border-[var(--line-strong)]">
              <div className="mono truncate text-sm">{r.site}</div>
              <div className="mt-0.5 text-xs text-[var(--muted)]">{r.kind}</div>
              <div className="mt-4 flex gap-4"><ScoreBadge label="SEO" value={r.seo} /><ScoreBadge label="AI" value={r.ai} /></div>
              <div className="mt-4 flex justify-between text-xs text-[var(--faint)]">
                <span>{fmt(r.urls)} URLs · {r.templates} templates</span>
                <span className="transition group-hover:translate-x-0.5">→</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Developers */}
      <section className="border-t border-[var(--line)]">
        <div className="mx-auto grid max-w-[1280px] items-start gap-10 px-4 py-20 lg:grid-cols-2">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight">Built for developers</h2>
            <p className="mt-2 text-[var(--muted)]">Catch SEO and GEO regressions in pull requests, run audits from your editor, or host the whole thing yourself.</p>
            <ul className="mt-6 space-y-3 text-sm">
              <li className="flex gap-3"><span className="text-[var(--good)]">✓</span><span><b className="font-medium">GitHub Action</b> — fails the PR when a template's score drops or its schema disappears.</span></li>
              <li className="flex gap-3"><span className="text-[var(--good)]">✓</span><span><b className="font-medium">MCP server</b> — <span className="mono text-xs">audit_site</span>, <span className="mono text-xs">generate_jsonld</span> and more, in Claude Code or Cursor.</span></li>
              <li className="flex gap-3"><span className="text-[var(--good)]">✓</span><span><b className="font-medium">Self-host</b> — <span className="mono text-xs">docker compose up</span>: FastAPI, Postgres, Redis, Next.js.</span></li>
            </ul>
            <a href="https://github.com/jaylahoti" target="_blank" rel="noreferrer" className="btn mt-6">View on GitHub →</a>
          </div>
          <CodeBlock label=".github/workflows/seogeo-audit-kit.yml" code={GH_ACTION} />
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-[var(--line)]">
        <div className="mx-auto max-w-3xl px-4 py-20">
          <h2 className="mb-6 text-3xl font-semibold tracking-tight">Questions</h2>
          <div className="divide-y divide-[var(--line)] border-y border-[var(--line)]">
            {FAQ.map(([q, a]) => (
              <details key={q} className="group py-4">
                <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium">
                  {q}<span className="text-[var(--faint)] transition group-open:rotate-45">+</span>
                </summary>
                <p className="mt-2 text-sm text-[var(--muted)]">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t border-[var(--line)] bg-[var(--sunken)]">
        <div className="mx-auto max-w-2xl px-4 py-20 text-center">
          <h2 className="text-3xl font-semibold tracking-tight">See your templates</h2>
          <p className="mb-6 mt-2 text-[var(--muted)]">Paste a sitemap. Results in about 90 seconds.</p>
          <AuditForm />
        </div>
      </section>
    </main>
  );
}
