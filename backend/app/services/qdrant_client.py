import logging
from qdrant_client import AsyncQdrantClient
from app.core.config import settings

logger = logging.getLogger(__name__)

_client: AsyncQdrantClient | None = None


async def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.qdrant_url)
        logger.info("Qdrant client created: %s", settings.qdrant_url)
    return _client


async def close_qdrant() -> None:
    global _client
    if _client:
        await _client.close()
        _client = None
