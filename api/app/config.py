from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    psi_api_key: str = ""  # optional free Google key for PageSpeed Insights; raises the quota
    max_urls: int = 5000
    max_sitemaps: int = 50
    max_page_bytes: int = 5_000_000
    max_sitemap_bytes: int = 50_000_000  # sitemaps can legally be 50 MB uncompressed
    fetch_timeout_s: float = 15.0
    max_redirects: int = 5
    user_agent: str = "SEOGEOAuditKitBot/0.1 (+https://github.com/jaylahoti/seogeo-audit-kit)"
    cors_origins: str = "http://localhost:3001"


settings = Settings()
