# TemplateScope

Per-template SEO + AI-readiness (GEO) audits for programmatic SEO sites. Open source (MIT).
Full scope: `FEATURES.md`.

## Layout
- `api/` Python 3.12, FastAPI, uv. Pipeline in `app/pipeline/runner.py`; each stage emits
  running/done events streamed over SSE (`GET /audits/{id}/events`).
  - `app/net/safe_fetch.py` — the ONLY way to fetch user-supplied URLs (SSRF guard, IP pinning, size caps).
  - `app/ingest/` — robots.txt (incl. AI-crawler policy), llms.txt, sitemaps (family-aware sampling + weights).
  - `app/ml/url_patterns.py` — template detection signal 1 (URL structure). Signal 2 (DOM MinHash + HDBSCAN) is next.
  - `app/store.py` — in-memory store; Postgres replaces it behind the same interface.
- `web/` Next.js 15 + Tailwind v4 UI. Currently renders sample data from `lib/mock.ts`.

## Rules
- Never fetch a user URL with anything but `safe_get`. Never follow redirects outside it.
- Respect robots.txt for page crawling. Identify as TemplateScopeBot.
- Never copy code, data, prompts, or internal docs from other companies' codebases into this repo
  (including the author's employer). Ideas and public best practices are fine; write everything fresh.
- Every Claude call records model, tokens, cost and ms in the stage event. Keep costs visible.
- Tests: `cd api && uv run pytest`. Lint: `uv run ruff check app tests`.

## Run
- api: `cd api && uv sync && cp .env.example .env && uv run uvicorn app.main:app --reload --port 8001`
- web: `cd web && pnpm install && pnpm dev --port 3001`
- Try it: `curl -X POST localhost:8001/audits -H 'Content-Type: application/json' -d '{"url":"https://example.com"}'`
