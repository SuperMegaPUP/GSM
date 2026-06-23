import asyncio
import logging
from app.services.vector_indexer import get_embedding_model

logger = logging.getLogger(__name__)


async def embed_text(text: str) -> list[float]:
    model = get_embedding_model()
    if model is None:
        raise RuntimeError("Embedding model not available")
    return list(model.embed([text]))[0].tolist()


async def embed_batch(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    if model is None:
        raise RuntimeError("Embedding model not available")
    return [v.tolist() for v in model.embed(texts)]
