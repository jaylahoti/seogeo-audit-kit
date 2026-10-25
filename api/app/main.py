import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.monitoring import scheduler
from app.routers import audits


@asynccontextmanager
async def lifespan(_app: FastAPI):
    task = asyncio.create_task(scheduler(audits.start_audit))  # scheduled re-audits
    yield
    task.cancel()


app = FastAPI(title="SEOGEO Audit Kit API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
)
app.include_router(audits.router)
app.include_router(audits.monitors)


@app.get("/health")
def health():
    return {"ok": True}
