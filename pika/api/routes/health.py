"""GET /health"""
from fastapi import APIRouter
from pika.api.schemas import HealthResponse
import pika

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    from pika.infra.db import DATABASE_URL
    from pika.config.loader import get_settings

    cfg = get_settings()
    db_type = "postgresql" if DATABASE_URL.startswith("postgresql") else "sqlite"
    vdb_provider = cfg.get("vectordb", {}).get("provider", "lancedb")
    cache_info = "l1" + ("+redis" if __import__("os").getenv("REDIS_URL") else "")

    return HealthResponse(
        status="ok",
        version=pika.__version__,
        db=db_type,
        vectordb=vdb_provider,
        cache=cache_info,
    )
