# TemplateScope — features

The SEO + GEO platform for programmatic sites: one tool instead of a crawler, a GEO tracker
and an AI-visibility tool — and everything is reported **per template**, so one fix covers
thousands of pages.

Status key: ✅ built · 🟡 in progress · ⬜ not started

## Stage 1 — Audit (Day 1)

### Foundation
- ✅ SSRF-safe fetcher: private/metadata IPs blocked, every redirect re-checked, IP pinning, size caps
- ✅ robots.txt: sitemap discovery, crawl permission
- ✅ Sitemaps: indexes, gzip, family-aware sampling across numbered files, weighted page estimates
- ✅ Template detection, signal 1: URL patterns ({id}, {uuid}, {slug}, {date}), facet-sibling merge, absorption
- ✅ Polite page crawler: robots.txt + Crawl-delay respected, per-host concurrency + pacing, timeouts
- ✅ Template detection, signal 2: shallow tag paths + heading skeleton → MinHash → HDBSCAN → close-cluster merge; splits/merges URL patterns; t-SNE map for the ML Lab
- ✅ Representative sampling per template (longest, shortest, newest, most unique, spread)

### Module 1 — Technical SEO (per template)
- ✅ Titles / meta descriptions: missing, duplicate, length
- ✅ Indexability: status, canonical (missing / points elsewhere), noindex (meta + header), sitemap redirects
- ⬜ Broken internal links, redirect chains
- ✅ Headings, image alt, word count, thin content, html lang, slow responses
- ✅ Boilerplate share within a template (unique 5-word shingles per page)
- ⬜ Internal linking: orphans, link depth
- ✅ Sitemap health: lastmod missing / stale, URLs that redirect / error / are noindexed
- ✅ hreflang self-reference

### Module 3 — Core Web Vitals
- ⬜ LCP / CLS / INP per template from PageSpeed Insights (lab) + CrUX (field, when available)

### Module 4 — AI-readiness (on-page GEO)
- ✅ AI-crawler policy: retrieval vs training bots, flags blocked retrieval bots
- ✅ llms.txt: llmstxt.org structure, sitemap pointer, no `## Optional`, no internal hosts
- ✅ JSON-LD: present, parses, main entity present, required props per type, no null/empty/placeholder values
- ✅ Freshness: `dateModified` present and recent
- ✅ Verdict sentence (heuristic; Claude confirms on Day 2)
- ✅ Facts up front (heuristic; Claude confirms on Day 2)
- ⬜ Placeholder values in visible text ("-%", "NaN", "undefined")
- ⬜ Fact-extraction test (Claude): key facts extracted and checked against page data
- ⬜ Title template vs question intent

### Module 7 — What AI sees
- ⬜ Fetch each template's samples raw (no JS, like most AI crawlers) vs rendered (headless browser)
- ⬜ Diff: facts, text, links and JSON-LD that only exist after JavaScript runs

### Module 12 — Fix generators
- ⬜ JSON-LD per template (validated before shown), verdict block, title template, summary block
- ⬜ llms.txt and robots.txt generators

## Stage 2 — AI + product (Day 2)
- ⬜ Judge agent: merge findings per template, rank by pages × severity; model router (rules → Haiku → Sonnet)
- ⬜ Web UI wired to the API: live progress over SSE, real report
- ⬜ Postgres + Redis job queue (arq) + worker; share links; PDF export
- ⬜ Module 13 — Question gaps: question families → template → page exists / answers / extractable
- ⬜ Module 10 — Monitoring: scheduled re-audits, per-template regressions, email/Slack alerts
- ⬜ Module 11 — GitHub Action (fail a PR when a template's score drops) + MCP server

## Stage 3 — Connect + track (Day 3)
- ⬜ Module 2 — Google Search Console (OAuth, read-only): indexed vs submitted and clicks per template, URL Inspection sample
- ⬜ Module 8 — Bing Webmaster: Bing indexation per template (ChatGPT search relies on Bing)
- ⬜ Module 9 — AI referral traffic: chatgpt.com / perplexity.ai / gemini / claude visits per template (GA4 or PostHog)
- ⬜ Module 5 — AI visibility tracking: fixed question set on a schedule, citation share, share of voice, competitors cited (Claude + optional ChatGPT / Perplexity / Gemini keys), own budget cap
- ⬜ Module 6 — AI crawler analytics: upload or stream access logs → which AI bots crawl which templates, how often, status codes
- ⬜ Evals: labelled sites, clustering ARI, check precision, judge κ — gate every deploy
- ⬜ Deploy: Vercel (web) + Railway/Fly (API + worker)

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
