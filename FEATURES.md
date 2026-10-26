# SEOGEO Audit Kit — features

The SEO + GEO platform for programmatic sites: one tool instead of a crawler, a GEO tracker
and an AI-visibility tool — and everything is reported **per template**, so one fix covers
thousands of pages.

Status key: ✅ built · 🟡 in progress · 🔜 coming soon · ⬜ not started

## Stage 1 — Audit (Day 1) ✅

### Foundation
- ✅ SSRF-safe fetcher: private/metadata IPs blocked, every redirect re-checked, IP pinning, size caps
- ✅ robots.txt: sitemap discovery, crawl permission
- ✅ Sitemaps: indexes, gzip, family-aware sampling across numbered files, weighted page estimates
- ✅ Smart sampling shown in the report (per-family breakdown) + "Count every page" for exact counts; limits configurable for self-hosting
- ✅ No sitemap: common sitemap paths, then link discovery from the home page
- ✅ Template detection, signal 1: URL patterns ({id}, {uuid}, {slug}, {date}), facet-sibling merge, absorption
- ✅ Polite page crawler: robots.txt + Crawl-delay respected, per-host concurrency + pacing, timeouts
- ✅ Template detection, signal 2: shallow tag paths + heading skeleton → MinHash → HDBSCAN → close-cluster merge; splits/merges URL patterns; t-SNE map for the ML Lab
- ✅ Representative sampling per template (longest, shortest, newest, most unique, spread)

### Module 1 — Technical SEO (per template)
- ✅ Titles / meta descriptions: missing, duplicate, length
- ✅ Indexability: status, canonical (missing / points elsewhere), noindex (meta + header), sitemap redirects
- ✅ Broken internal links and links to redirects (40 link targets probed per audit)
- ✅ Headings, image alt, word count, thin content, html lang, slow responses
- ✅ Boilerplate share within a template (unique 5-word shingles per page)
- ✅ Click depth per template (bounded crawl from the home page, 60 pages / 3 clicks)
- ⬜ Full orphan detection (needs a complete crawl or server logs)
- ✅ Sitemap health: lastmod missing / stale, URLs that redirect / error / are noindexed
- ✅ hreflang self-reference

### Module 3 — Core Web Vitals
- ✅ LCP / CLS / INP per template from PageSpeed Insights: field data (URL, then origin) or lab run; needs a free PSI_API_KEY

### Module 4 — AI-readiness (on-page GEO)
- ✅ AI-crawler policy: retrieval vs training bots, flags blocked retrieval bots
- ✅ llms.txt: llmstxt.org structure, sitemap pointer, no `## Optional`, no internal hosts
- ✅ JSON-LD: present, parses, main entity present, required props per type, no null/empty/placeholder values
- ✅ Freshness: `dateModified` present and recent
- ✅ Verdict sentence (heuristic; Claude confirms on Day 2)
- ✅ Facts up front (heuristic; Claude confirms on Day 2)
- ✅ Placeholder values in visible text ("-%", "NaN", "undefined", "{{…}}")
- ✅ Fact-extraction test (Claude Haiku): key facts in text and in JSON-LD, per page type
- ✅ Title template vs question intent (Claude)

### Module 7 — What AI sees
- ✅ Each template's sample fetched raw (no JS) vs rendered in headless Chromium, with every browser request checked against the SSRF guard
- ✅ Diff: text share, headings, links and JSON-LD that only exist after JavaScript runs

### Module 12 — Fix generators
- ✅ JSON-LD, verdict sentence and title template per page type (Claude Sonnet judge); JSON-LD validated before it's shown
- ✅ llms.txt and robots.txt generators (built from the audit's templates, sitemaps and current bot policy)

### GEO score
- ✅ GEO = Access 30% + Readiness 40% + Visibility 30%; missing parts are left out and marked partial
- ✅ Access from robots.txt policy, llms.txt, JavaScript-only content (page-weighted), click depth — every deduction listed
- ✅ Readiness from the AI-readiness checks, page-weighted (Claude's fact extraction joins on Day 2)
- ✅ Visibility from citation checks with web search (cited / found-not-cited / missing), weighted by sample size

## Stage 2 — AI + product (Day 2) ✅
- ✅ Judge (Sonnet, one call): summary and top fixes; router: rules → Haiku per page → Sonnet once; per-audit budget cap
- ✅ Web UI wired to the API: live progress over SSE, real report
- ✅ Saved audits (SQLite by default, Postgres via DATABASE_URL); share links survive restarts; PDF via print
- ⬜ Redis job queue + separate worker (only needed for multi-instance hosting)
- ✅ Module 13 — Question gaps: questions per page type → page answers it / facts extractable / AI cites the site
- ✅ Module 10 — Monitoring: compare with the previous audit (deterministic checks only), score history, scheduled re-audits, Slack-compatible webhook
- ✅ Explaining the AI/ML: live Claude cost meter while an audit runs; "Under the hood" view (page funnel, model routing, cost by step, every step labelled Code / ML / Browser / Claude); "Why?" on every Claude finding (what Claude was shown, what it answered, guardrail result); public /how-it-works page
- ✅ Module 11 — CLI with --fail-on rules, GitHub Action, MCP server (audit_site, get_report, get_page_type, check_page, get_llms_txt)

## Stage 3 — Connect + track (Day 3)
- 🔜 Module 2 — Google Search Console (OAuth, read-only): indexed vs submitted and clicks per template, URL Inspection sample — **Coming soon** (needs the site owner's account; sample preview shown)
- 🔜 Module 8 — Bing Webmaster: Bing indexation per template (ChatGPT search relies on Bing) — **Coming soon**
- 🔜 Module 9 — AI referral traffic: chatgpt.com / perplexity.ai / gemini / claude visits per template (GA4 or PostHog) — **Coming soon**
- ✅ Module 5 — AI visibility with Claude (questions from page checks, share of voice, competitors cited)
- ✅ Module 5 — other engines with your own keys: ChatGPT (Responses API + web search), Perplexity (Sonar), Gemini (Google Search grounding); same questions, pooled score, per-engine rows. Parsers tested on recorded response shapes; not yet run against live keys
- ✅ Module 6 — AI crawler analytics: upload an access log (nginx/Apache combined, Vercel or Cloudflare JSON, plain or .gz, ≤50 MB) → bots × page types, errors, llms.txt fetches, AI coverage per page type; Google/Bing/Apple verified by forward-confirmed reverse DNS; only totals are stored; "Try a synthetic log" for demos
- ✅ Evals: 3 generated sites with known answers → page-type ARI (vs URL-only baseline), page-count error, rule-check precision/recall, heuristic vs Claude (accuracy, Cohen's κ); gate in the test suite; CI workflow runs it on every push
- ✅ Public-demo limits: 3 audits per visitor per day (salted IP hash), daily Claude budget (audits fall back to no-Claude), localhost exempt
- ✅ Docker: API and web Dockerfiles; `docker compose up` runs API + web + Postgres
- ⬜ Deploy: Vercel (web) + Railway/Fly (API)

## Bring your own key (self-hosted)
The hosted demo uses only Claude and free APIs. Features that need paid third-party keys are
fully built; in the demo they show a labelled sample report and say which key unlocks them:
- ChatGPT / Perplexity / Gemini citation tracking (module 5): OPENAI_API_KEY, PERPLEXITY_API_KEY, GEMINI_API_KEY
- Optional: DataForSEO for keyword volumes

## Not building
- Backlink and keyword-volume databases (need paid data; optional DataForSEO integration later)
- Rank tracking for arbitrary keywords (Search Console covers the user's own site)

## Needs from the owner
- Anthropic API key with a monthly spend limit (Day 2) — the hosted demo runs on Claude + free APIs only
- Google Cloud OAuth client; test users until Google verifies the app (Day 3)
- Bing Webmaster API key; optional OpenAI / Perplexity / Gemini keys (Day 3)
- A sample access log (Vercel / Cloudflare / nginx) for module 6
- ~1 hour to confirm template labels on ~5 eval sites
- Docker Desktop running (Postgres + Redis); Vercel + Railway accounts
