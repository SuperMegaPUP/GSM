import logging
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from app.core.config import settings
from app.services.vector_indexer import get_embedding_model

logger = logging.getLogger(__name__)


def _sales_collection(tenant_id: UUID) -> str:
    return f"sales_objections_{tenant_id}"


async def _ensure_sales_collection(
    client: AsyncQdrantClient,
    collection: str,
) -> None:
    existing = await client.get_collections()
    names = [c.name for c in existing.collections]
    if collection not in names:
        await client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Коллекция %s создана", collection)


async def index_sales_objections(
    tenant_id: UUID,
    objections_data: list[dict],
    qdrant_client: AsyncQdrantClient,
) -> int:
    collection = _sales_collection(tenant_id)
    await _ensure_sales_collection(qdrant_client, collection)

    model = get_embedding_model()
    points: list[PointStruct] = []

    for i, entry in enumerate(objections_data):
        text = f"Возражение: {entry.get('objection', '')}. Аргумент: {entry.get('core_argument', '')}. Ответ: {entry.get('successful_reply', '')}"

        points.append(
            PointStruct(
                id=f"{tenant_id}_{i}",
                vector=list(model.embed([text]))[0].tolist(),
                payload={
                    "tenant_id": str(tenant_id),
                    "category": entry.get("category", "Общее"),
                    "objection": entry.get("objection", ""),
                    "core_argument": entry.get("core_argument", ""),
                    "successful_reply": entry.get("successful_reply", ""),
                },
            )
        )

    if points:
        await qdrant_client.upsert(
            collection_name=collection,
            points=points,
        )

    logger.info(
        "Индексация базы возражений завершена: %d записей в %s",
        len(points), collection,
    )
    return len(points)
