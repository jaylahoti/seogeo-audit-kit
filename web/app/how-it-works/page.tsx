import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "How it works",
  description: "How SEOGEO Audit Kit audits a million-page site for about $0.20: code and ML on every page, Claude only on samples, with guardrails on every answer.",
};

type Kind = "code" | "ml" | "browser" | "claude";
const KIND: Record<Kind, { label: string; color: string }> = {
  code: { label: "Code", color: "var(--line-strong)" },
  ml: { label: "ML", color: "var(--good)" },
  browser: { label: "Browser", color: "var(--warn)" },
  claude: { label: "Claude", color: "var(--accent)" },
};

function Chip({ k }: { k: Kind }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[var(--line)] px-2 py-0.5 text-[11px] text-[var(--muted)]">
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: KIND[k].color }} />{KIND[k].label}
    </span>
  );
}

const STEPS: { kind: Kind; title: string; does: string; why: string }[] = [
  { kind: "code", title: "Read robots.txt, llms.txt and the sitemaps",
    does: "Follows sitemap indexes and samples files from every family (numbered files, per-city files and so on), then scales the counts back up.",
    why: "A 1.3M-page site has hundreds of sitemap files. Reading a fair sample gets the page count within about 1%; “Count every page” reads them all when you need the exact number." },
  { kind: "ml", title: "Group URLs into page types",
    does: "Turns URLs into patterns like /building/{slug}, then fetches a few pages per pattern and compares their structure (tag paths and heading outline) with MinHash. HDBSCAN clusters pages that share a layout.",
    why: "URLs alone over-split or under-split. One pattern can hide two layouts, and two patterns can be the same page. Structure settles it, with no labels to train on." },
  { kind: "code", title: "Fetch samples and run 24 rule checks",
    does: "About 6 pages per page type: titles, canonicals, headings, JSON-LD and its required properties, placeholders like “-%”, freshness, internal links and broken links.",
    why: "Pages built from one template share its bugs, so a handful of samples shows the problem for all of them. Rules are free, fast and exact, so they go first." },
  { kind: "browser", title: "Render with and without JavaScript, measure Core Web Vitals",
    does: "Headless Chromium compares what a crawler that doesn't run JavaScript sees against the full page. Core Web Vitals come from Chrome field data via PageSpeed Insights.",
    why: "Most AI crawlers don't run JavaScript. If the facts only appear after hydration, they don't exist for ChatGPT or Claude." },
  { kind: "claude", title: "Claude reads the sample pages",
    does: "Claude Haiku, one call per sample page: which key facts a page of this type should state, whether this page states them in text and in JSON-LD, whether there's one quotable summary sentence, and which questions it answers.",
    why: "Rules can't tell whether “Rated 4.2 by 38 renters” is a fact or a placeholder, or whether a page answers what people actually ask. A small, fast model is enough for this reading task." },
  { kind: "claude", title: "Ask real questions with web search",
    does: "Claude Haiku with the web search tool answers the questions people ask about your page types and records which sites it cites. It keeps asking until it has 8 answers that actually searched.",
    why: "This is the closest free signal to “does AI search quote us?”. Answers given from memory, without a search, are marked and not scored." },
  { kind: "claude", title: "Judge everything once and write the fixes",
    does: "Claude Sonnet reads a digest of every finding, ranks the fixes by pages covered and severity, and writes the code for each page type: JSON-LD, a summary block, a title pattern.",
    why: "Ranking trade-offs across the whole site needs judgement, so the bigger model runs here, once, not once per page." },
  { kind: "code", title: "Score, compare and alert",
    does: "SEO, AI readiness and GEO scores per page type, compared with the last saved audit. Scheduled monitors post to Slack when a deploy breaks a template.",
    why: "Comparisons use only the deterministic checks, so the alert means the site changed, not that a model answered differently." },
];

const ROUTING = [
  ["Page checks", "Claude Haiku 5.5", "~60 calls", "Structured output, low effort", "~$0.05"],
  ["AI visibility", "Claude Haiku 5.5 + web search", "8–16 calls", "$0.01 per search", "~$0.10"],
  ["Judge and fixes", "Claude Sonnet 5.5", "1 call", "Structured output, medium effort", "~$0.05"],
];

const GUARDRAILS = [
  ["Structured output only", "Every Claude call returns a fixed schema (Pydantic). A malformed answer is rejected, never parsed by guesswork."],
  ["Quotes must exist on the page", "When Claude says “this is the quotable sentence”, the sentence is searched for in the page text. If it isn't there, it's thrown away."],
  ["Generated JSON-LD is validated", "Placeholders are filled with sample values, then it must parse, have a schema.org @type, and include the required properties. Failing fixes aren't shown."],
  ["Unsearched answers aren't scored", "If the model answers from memory instead of searching, the answer is kept for reference but left out of the visibility score. The score shows its confidence."],
  ["A hard budget per audit", "Before each call, the worst-case cost (full output length) must fit in what's left of the $0.50 cap. Every call records model, tokens, cost and time."],
  ["Show the evidence", "Each Claude finding has a “Why?” button: what Claude was shown, what it answered, and whether the guardrail passed."],
];

const LIMITS = [
  "It samples pages per page type. A bug that hits one page in a thousand of the same template can be missed.",
  "AI visibility uses Claude's web search. ChatGPT, Perplexity and Gemini need your own keys when you self-host.",
  "Search Console, Bing and AI referral traffic need you to connect your accounts.",
  "Page types are found without labels, so two near-identical layouts can still be merged. The report shows the clustering so you can check.",
];

export default function HowItWorks() {
  return (
    <main>
      <section className="mx-auto max-w-[1080px] px-4 pb-12 pt-16 lg:pt-20">
        <span className="pill bg-[var(--accent-soft)] text-[var(--accent)]">How it works</span>
        <h1 className="mt-5 max-w-3xl text-4xl font-semibold leading-[1.1] tracking-tight md:text-5xl">
          A million pages, about 60 Claude calls.
        </h1>
        <p className="mt-5 max-w-2xl text-lg text-[var(--muted)]">
          Sending every page of a large site to a language model would cost thousands of dollars per audit. This tool runs
          code and ML on everything, and only shows Claude a small, well-chosen sample, then checks Claude's answers before they reach the report.
        </p>
        <div className="mt-8 grid gap-3 sm:grid-cols-3">
          <div className="card p-4"><div className="text-xs text-[var(--muted)]">Pages on a real test site</div><div className="mono mt-1 text-2xl font-semibold">~1,350,000</div></div>
          <div className="card p-4"><div className="text-xs text-[var(--muted)]">Claude cost of one audit</div><div className="mono mt-1 text-2xl font-semibold">~$0.20</div></div>
          <div className="card p-4"><div className="text-xs text-[var(--muted)]">Every page through a large model</div><div className="mono mt-1 text-2xl font-semibold">~$14,900</div></div>
        </div>
      </section>

      <section className="border-t border-[var(--line)]">
        <div className="mx-auto max-w-[1080px] px-4 py-16">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <h2 className="text-3xl font-semibold tracking-tight">The pipeline</h2>
            <div className="flex flex-wrap gap-2">{(Object.keys(KIND) as Kind[]).map((k) => <Chip key={k} k={k} />)}</div>
          </div>
          <p className="mt-2 max-w-2xl text-[var(--muted)]">Cheapest tool first. Each step narrows what the next, more expensive step has to look at.</p>
          <ol className="mt-8 space-y-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="card grid gap-4 p-5 md:grid-cols-[48px_minmax(0,1fr)_minmax(0,1fr)]">
                <div className="mono text-sm text-[var(--faint)]">0{i + 1}</div>
                <div>
                  <div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">{s.title}</h3><Chip k={s.kind} /></div>
                  <p className="mt-1.5 text-sm text-[var(--muted)]">{s.does}</p>
                </div>
                <p className="text-sm text-[var(--muted)] md:border-l md:border-[var(--line)] md:pl-4"><span className="text-xs font-medium text-[var(--faint)]">Why · </span>{s.why}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="border-t border-[var(--line)] bg-[var(--sunken)]">
        <div className="mx-auto max-w-[1080px] px-4 py-16">
          <h2 className="text-3xl font-semibold tracking-tight">Model routing</h2>
          <p className="mt-2 max-w-2xl text-[var(--muted)]">The small model does the many repetitive reads. The bigger model is called once, where judgement matters.</p>
          <div className="card mt-6 overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="text-left text-xs text-[var(--faint)]">
                <tr>{["Step", "Model", "Calls per audit", "How", "Typical cost"].map((h) => <th key={h} className="px-4 py-2.5 font-normal">{h}</th>)}</tr>
              </thead>
              <tbody className="divide-y divide-[var(--line)]">
                {ROUTING.map((r) => (
                  <tr key={r[0]}>{r.map((c, i) => <td key={i} className={`px-4 py-2.5 ${i === 1 || i === 4 ? "mono text-xs" : ""}`}>{c}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-[var(--faint)]">Everything else (sitemaps, clustering, rules, rendering, scoring) costs $0. Each report's “Under the hood” view shows the real numbers for that audit.</p>
        </div>
      </section>

      <section className="border-t border-[var(--line)]">
        <div className="mx-auto max-w-[1080px] px-4 py-16">
          <h2 className="text-3xl font-semibold tracking-tight">Guardrails</h2>
          <p className="mt-2 max-w-2xl text-[var(--muted)]">A model's answer is treated as a claim to check, not a fact.</p>
          <div className="mt-6 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {GUARDRAILS.map(([t, d]) => (
              <div key={t} className="card p-4">
                <h3 className="text-sm font-semibold">{t}</h3>
                <p className="mt-1 text-sm text-[var(--muted)]">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-t border-[var(--line)] bg-[var(--sunken)]">
        <div className="mx-auto max-w-[1080px] px-4 py-16">
          <h2 className="text-3xl font-semibold tracking-tight">What it doesn't do</h2>
          <ul className="mt-6 max-w-3xl space-y-3 text-sm text-[var(--muted)]">
            {LIMITS.map((l) => <li key={l} className="flex gap-3"><span className="text-[var(--faint)]">—</span><span>{l}</span></li>)}
          </ul>
        </div>
      </section>

      <section className="border-t border-[var(--line)]">
        <div className="mx-auto max-w-2xl px-4 py-16 text-center">
          <h2 className="text-3xl font-semibold tracking-tight">See it on your site</h2>
          <p className="mb-6 mt-2 text-[var(--muted)]">Run an audit, then open “Under the hood” in the report.</p>
          <div className="flex flex-wrap justify-center gap-3">
            <Link href="/#audit" className="btn btn-primary">Run an audit</Link>
            <Link href="/report/demo-nestlist" className="btn">Open the sample report</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
