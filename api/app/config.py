from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    psi_api_key: str = ""
    # Optional, self-hosted: citation tracking in other AI engines (billed to these keys).
    openai_api_key: str = ""
    perplexity_api_key: str = ""
    gemini_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    perplexity_model: str = "sonar"
    gemini_model: str = "gemini-2.5-flash"
    # Claude: models per job and a hard cost ceiling per audit (USD).
    page_model: str = "claude-haiku-5-5"  # per-page checks and citation searches
    judge_model: str = "claude-sonnet-5-5"  # one judge-and-fixes call per audit
    max_audit_cost_usd: float = 0.50
    # Public-demo limits. Requests from this machine (localhost) are never limited.
    free_audits_per_day: int = 3  # per visitor, rolling 24 hours; 0 = no limit
    daily_budget_usd: float = 5.0  # Claude spend across all audits, rolling 24 hours; 0 = no cap
    trust_proxy: bool = False  # read the visitor IP from X-Forwarded-For (set true behind Railway/Fly/nginx)
    visitor_salt: str = "seogeo"  # visitor IPs are stored only as salted hashes
    render_pages: bool = True  # headless-browser "What AI sees" step (CI can turn it off)
    claude_templates: int = 12  # largest page types that get Claude page checks
    visibility_answers: int = 8  # searched answers to collect for the visibility score
    visibility_max_questions: int = 16  # stop asking after this many (unsearched answers are cheap)  # optional free Google key for PageSpeed Insights; raises the quota
    # Smart sampling limits. The hosted demo keeps these defaults; self-hosters can raise them.
    max_urls: int = 5000  # sitemap URLs kept for template detection
    max_sitemaps: int = 50  # sitemap files read per audit (the rest are estimated)
    crawl_per_template: int = 6  # pages fetched per URL pattern for layout detection
    samples_per_template: int = 5  # pages each check runs on
    max_count_files: int = 2000  # ceiling for "Count every page"
    max_page_bytes: int = 5_000_000
    max_sitemap_bytes: int = 50_000_000  # sitemaps can legally be 50 MB uncompressed
    fetch_timeout_s: float = 15.0
    max_redirects: int = 5
    user_agent: str = "SEOGEOAuditKitBot/0.1 (+https://github.com/jaylahoti/seogeo-audit-kit)"
    cors_origins: str = "http://localhost:3001"
    # Saved audits. SQLite file by default; set a postgresql+psycopg:// URL in production.
    database_url: str = "sqlite:///./audits.db"


settings = Settings()
