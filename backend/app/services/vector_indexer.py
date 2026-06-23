import logging
from typing import Optional
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.models.models import (
    CarBrand,
    CarModel,
    CarVariant,
    Fluid,
    Recommendation,
)

logger = logging.getLogger(__name__)

NODE_LABELS: dict[str, str] = {
    "ENGINE": "Двигатель",
    "MANUAL_TRANSMISSION": "МКПП",
    "AUTO_TRANSMISSION": "АКПП",
    "CVT": "Вариатор",
    "TRANSFER_CASE": "Раздатка",
    "FRONT_DIFF": "Передний мост",
    "REAR_DIFF": "Задний мост",
    "STEERING": "ГУР",
    "BRAKE": "Тормозная система",
    "COOLANT": "Охлаждение",
}


# =============================================================
# Синглтон модели эмбеддингов
# =============================================================

_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from fastembed import TextEmbedding

            _embedding_model = TextEmbedding(
                model_name=settings.embedding_model,
            )
            logger.info(
                "Модель эмбеддингов %s загружена",
                settings.embedding_model,
            )
        except ImportError:
            logger.warning(
                "fastembed не установлен — векторизация пропущена. "
                "Установите: pip install fastembed"
            )
    return _embedding_model


# =============================================================
# Вспомогательные функции
# =============================================================


def _collection_name(tenant_id: UUID) -> str:
    return f"recommendations_{tenant_id}"


def _build_embedding_text(
    brand_name: str,
    model_name: str,
    engine_code: Optional[str],
    engine_volume: Optional[float],
    node_type: str,
    fluid_brand: Optional[str],
    fluid_name: str,
    viscosity: Optional[str],
    oem_approvals: list,
) -> str:
    parts = [
        f"Рекомендация для {brand_name} {model_name}",
    ]
    if engine_code:
        parts.append(engine_code)
    if engine_volume:
        parts.append(f"{engine_volume}L")
    node_label = NODE_LABELS.get(node_type, node_type)
    parts.append(node_label)
    parts.append(f"Масло {fluid_brand or ''} {fluid_name}".strip())
    if viscosity:
        parts.append(f"вязкость {viscosity}")
    if oem_approvals:
        parts.append(f"допуски {', '.join(str(a) for a in oem_approvals)}")
    return ". ".join(parts)


def _build_query_text(
    brand: Optional[str] = None,
    model: Optional[str] = None,
    year: Optional[int] = None,
    engine_code: Optional[str] = None,
    engine_volume: Optional[float] = None,
) -> str:
    parts = []
    if brand and model:
        parts.append(f"Масло для {brand} {model}")
    elif brand:
        parts.append(f"Масло для {brand}")
    elif model:
        parts.append(f"Масло для модели {model}")
    else:
        parts.append("Рекомендуемое моторное масло")
    if engine_code:
        parts.append(f"двигатель {engine_code}")
    if engine_volume:
        parts.append(f"объём {engine_volume} литра")
    if year:
        parts.append(f"{year} года выпуска")
    return ". ".join(parts)


# =============================================================
# Создание / проверка коллекции
# =============================================================


async def _ensure_collection(
    client: AsyncQdrantClient,
    collection: str,
    vector_size: int = 384,
) -> None:
    existing = await client.get_collections()
    names = [c.name for c in existing.collections]
    if collection not in names:
        await client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Коллекция %s создана (%d dim)", collection, vector_size)


# =============================================================
# Основная функция индексации
# =============================================================


async def index_recommendations_to_qdrant(
    tenant_id: UUID,
    db: AsyncSession,
    qdrant_client: AsyncQdrantClient,
    rec_ids: Optional[list[UUID]] = None,
) -> int:
    collection = _collection_name(tenant_id)
    await _ensure_collection(qdrant_client, collection, settings.embedding_dim)

    stmt = (
        select(Recommendation)
        .options(
            joinedload(Recommendation.fluid),
            joinedload(Recommendation.car_variant)
            .joinedload(CarVariant.model)
            .joinedload(CarModel.brand),
        )
        .where(Recommendation.company_id == tenant_id)
    )
    if rec_ids is not None:
        if not rec_ids:
            logger.info("Нет новых рекомендаций — индексация Qdrant пропущена")
            return 0
        stmt = stmt.where(Recommendation.id.in_(rec_ids))

    result = await db.execute(stmt)
    recs: list[Recommendation] = list(result.unique().scalars().all())

    if not recs:
        logger.info("Нет рекомендаций для индексации tenant=%s", tenant_id)
        return 0

    model = get_embedding_model()
    if model is None:
        logger.warning("Векторизация пропущена: модель эмбеддингов не доступна")
        return 0

    texts: list[str] = []
    point_data: list[tuple] = []

    for rec in recs:
        fluid = rec.fluid
        variant = rec.car_variant
        car_model = variant.model
        brand = car_model.brand

        text = _build_embedding_text(
            brand_name=brand.name_ru,
            model_name=car_model.name,
            engine_code=variant.engine_code,
            engine_volume=variant.engine_volume,
            node_type=rec.node_type.value,
            fluid_brand=fluid.brand,
            fluid_name=fluid.canonical_name,
            viscosity=fluid.viscosity_sae,
            oem_approvals=fluid.oem_approvals or [],
        )

        texts.append(text)
        point_data.append((rec, fluid, variant, car_model, brand))

    batch_size = 100
    points: list[PointStruct] = []

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_data = point_data[i : i + batch_size]

        embeddings = list(model.embed(batch_texts))

        for (rec, fluid, variant, car_model, brand), embedding in zip(batch_data, embeddings):
            points.append(
                PointStruct(
                    id=str(rec.id),
                    vector=embedding.tolist(),
                    payload={
                        "tenant_id": str(tenant_id),
                        "variant_id": str(variant.id),
                        "fluid_id": str(fluid.id),
                        "node_type": rec.node_type.value,
                        "is_oem": rec.is_oem_recommendation,
                        "brand_name": brand.name_ru,
                        "model_name": car_model.name,
                        "engine_code": variant.engine_code,
                        "engine_volume": variant.engine_volume,
                        "fluid_canonical_name": fluid.canonical_name,
                        "fluid_brand": fluid.brand,
                        "fluid_product_line": fluid.product_line,
                        "fluid_type": fluid.fluid_type.value,
                        "viscosity_sae": fluid.viscosity_sae,
                        "api_class": fluid.api_class,
                        "acea_class": fluid.acea_class,
                        "oem_approvals": fluid.oem_approvals or [],
                        "volume_liters": rec.volume_liters,
                        "volume_with_filter": rec.volume_with_filter,
                        "is_oem_recommendation": rec.is_oem_recommendation,
                        "oem_specification": rec.oem_specification,
                        "confidence_score": rec.confidence_score,
                    },
                )
            )

        if len(points) >= batch_size:
            await qdrant_client.upsert(
                collection_name=collection,
                points=points,
            )
            points.clear()

    if points:
        await qdrant_client.upsert(
            collection_name=collection,
            points=points,
        )

    logger.info(
        "Qdrant индексация завершена: %d точек в коллекцию %s",
        len(recs),
        collection,
    )
    return len(recs)
