# SEOGEO Audit Kit API: FastAPI + headless Chromium for "What AI sees".
FROM python:3.12.7-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.0 /uv /bin/uv
# Browsers outside /root, so the image also works on hosts that run containers as a non-root user.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH" PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
# Chromium and the system libraries it needs.
RUN playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/* && chmod -R a+rX /ms-playwright

COPY app ./app
RUN uv sync --frozen --no-dev

# SQLite lives here unless DATABASE_URL points at Postgres. Mount a volume to keep reports.
ENV DATABASE_URL=sqlite:////data/audits.db
RUN mkdir -p /data && chmod 777 /data
EXPOSE 8001
# Railway/Fly set $PORT.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001} --proxy-headers --forwarded-allow-ips='*'"]
