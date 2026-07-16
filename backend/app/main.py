from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.config import get_settings
from app.db import engine
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.routers.calls import router as calls_router
from app.routers.compare import router as compare_router
from app.routers.evals import router as evals_router
from app.routers.ingest import router as ingest_router
from app.routers.stats import router as stats_router

settings = get_settings()
configure_logging()

app = FastAPI(title="Debrief API", version="0.1.0")
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)
app.include_router(ingest_router)
app.include_router(calls_router)
app.include_router(stats_router)
app.include_router(evals_router)
app.include_router(compare_router)


@app.get("/healthz")
async def healthz() -> JSONResponse:
    db_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = False
    try:
        redis = Redis.from_url(settings.redis_url)
        await redis.ping()
        await redis.aclose()
        redis_ok = True
    except Exception:
        redis_ok = False

    healthy = db_ok and redis_ok
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={
            "status": "ok" if healthy else "degraded",
            "db": db_ok,
            "redis": redis_ok,
            "build_sha": settings.git_sha,
        },
    )
