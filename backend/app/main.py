from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from redis import asyncio as aioredis

from app.core.config import settings
from app.core.database import engine, async_session, text
from app.core.minio_client import ensure_bucket_exists
from app.routers import auth, catalog, imports


# =============================================================
# Глобальные клиенты (инициализация при старте)
# =============================================================

redis_client: aioredis.Redis | None = None
qdrant_client: AsyncQdrantClient | None = None

class AppState:
    redis: aioredis.Redis | None = None
    qdrant: AsyncQdrantClient | None = None
    started_at: datetime | None = None


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / Shutdown."""
    state.started_at = datetime.utcnow()
    state.redis = aioredis.from_url(
        settings.redis_url, decode_responses=True
    )
    state.qdrant = AsyncQdrantClient(url=settings.qdrant_url)

    async with async_session() as session:
        await session.execute(text("SELECT 1"))

    await ensure_bucket_exists()

    yield

    if state.redis:
        await state.redis.close()
    if state.qdrant:
        await state.qdrant.close()
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — для разработки с Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================
# Pydantic модели для ответов
# =============================================================

class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    database: str
    redis: str
    qdrant: str
    minio: str


# =============================================================
# Роутеры
# =============================================================

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(imports.router)


# =============================================================
# Эндпоинты
# =============================================================

@app.get("/api/v1/health", response_model=HealthResponse)
async def health_check():
    """Healthcheck — проверка всех зависимостей."""
    uptime = (datetime.utcnow() - state.started_at).total_seconds() if state.started_at else 0

    # Проверка БД
    db_status = "ok"
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    # Проверка Redis
    redis_status = "ok"
    try:
        if state.redis:
            await state.redis.ping()
        else:
            redis_status = "not_initialized"
    except Exception:
        redis_status = "error"

    # Проверка Qdrant
    qdrant_status = "ok"
    try:
        if state.qdrant:
            await state.qdrant.health_check()
        else:
            qdrant_status = "not_initialized"
    except Exception:
        qdrant_status = "error"

    # Проверка MinIO
    minio_status = "ok"
    try:
        from app.core.minio_client import minio_client
        import asyncio
        await asyncio.to_thread(minio_client.bucket_exists, "excel-imports")
    except Exception:
        minio_status = "error"

    return HealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        version="0.1.0",
        uptime_seconds=round(uptime, 2),
        database=db_status,
        redis=redis_status,
        qdrant=qdrant_status,
        minio=minio_status,
    )


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
