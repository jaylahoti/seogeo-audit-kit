from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    psi_api_key: str = ""
    # Claude: models per job and a hard cost ceiling per audit (USD).
    page_model: str = "claude-haiku-5-5"  # per-page checks and citation searches
    judge_model: str = "claude-sonnet-5-5"  # one judge-and-fixes call per audit
    max_audit_cost_usd: float = 0.50
    claude_templates: int = 12  # largest page types that get Claude page checks
    visibility_questions: int = 10  # citation searches per audit  # optional free Google key for PageSpeed Insights; raises the quota
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
