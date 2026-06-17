import logging
from typing import Optional
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.schemas.search_schemas import (
    CarSearchSchema,
    FluidSearchResult,
    NodeGroupResult,
    SearchResponse,
)
from app.models.models import (
    CarBrand,
    CarModel,
    CarVariant,
    Fluid,
    Recommendation,
)
from app.services.vector_indexer import (
    NODE_LABELS,
    _build_query_text,
    _collection_name,
    get_embedding_model,
)

logger = logging.getLogger(__name__)


# =============================================================
# Точный поиск через SQL
# =============================================================


async def _search_exact_sql(
    params: CarSearchSchema,
    tenant_id: UUID,
    db: AsyncSession,
) -> Optional[SearchResponse]:
    """Ищет рекомендации точным совпадением brand → model → variant."""

    brand_stmt = select(CarBrand).where(
        CarBrand.company_id == tenant_id,
        CarBrand.name_ru.ilike(params.brand),
    )
    brand_result = await db.execute(brand_stmt)
    brand = brand_result.scalars().first()
    if not brand:
        return None

    model_stmt = select(CarModel).where(
        CarModel.company_id == tenant_id,
        CarModel.brand_id == brand.id,
        CarModel.name.ilike(params.model),
    )
    if params.year:
        model_stmt = model_stmt.where(
            (CarModel.year_start.is_(None) | (CarModel.year_start <= params.year)),
            (CarModel.year_end.is_(None) | (CarModel.year_end >= params.year)),
        )
    model_result = await db.execute(model_stmt)
    car_model = model_result.scalars().first()
    if not car_model:
        return None

    variant_stmt = select(CarVariant).where(
        CarVariant.company_id == tenant_id,
        CarVariant.model_id == car_model.id,
    )
    if params.engine_code:
        variant_stmt = variant_stmt.where(
            CarVariant.engine_code.ilike(params.engine_code)
        )
    if params.engine_volume:
        variant_stmt = variant_stmt.where(
            CarVariant.engine_volume == params.engine_volume
        )
    variant_result = await db.execute(variant_stmt)
    variant = variant_result.scalars().first()
    if not variant:
        return None

    rec_stmt = (
        select(Recommendation)
        .options(joinedload(Recommendation.fluid))
        .where(
            Recommendation.company_id == tenant_id,
            Recommendation.car_variant_id == variant.id,
        )
    )
    rec_result = await db.execute(rec_stmt)
    recs: list[Recommendation] = list(rec_result.unique().scalars().all())

    if not recs:
        return None

    groups = _group_by_node(recs)

    return SearchResponse(
        found_by="exact_sql",
        variant_id=variant.id,
        brand=brand.name_ru,
        model=car_model.name,
        engine_code=variant.engine_code,
        engine_volume=variant.engine_volume,
        year_start=variant.year_start,
        year_end=variant.year_end,
        groups=groups,
    )


# =============================================================
# Семантический поиск через Qdrant
# =============================================================


async def _search_semantic_qdrant(
    params: CarSearchSchema,
    tenant_id: UUID,
    qdrant: AsyncQdrantClient,
) -> Optional[SearchResponse]:
    """Поиск аналогов через векторную базу Qdrant."""
    collection = _collection_name(tenant_id)

    try:
        collection_info = await qdrant.get_collection(collection)
    except Exception:
        logger.warning("Коллекция %s не найдена", collection)
        return None

    if collection_info.status != "green":
        logger.warning("Коллекция %s не активна (%s)", collection, collection_info.status)
        return None

    query_text = _build_query_text(
        brand=params.brand,
        model=params.model,
        year=params.year,
        engine_code=params.engine_code,
        engine_volume=params.engine_volume,
    )

    model = get_embedding_model()
    query_vector = model.encode(query_text).tolist()

    search_result = await qdrant.search(
        collection_name=collection,
        query_vector=query_vector,
        limit=20,
        query_filter=Filter(
            must=[
                FieldCondition(
                    key="tenant_id",
                    match=MatchValue(value=str(tenant_id)),
                ),
            ]
        ),
    )

    if not search_result:
        return None

    payload = search_result[0].payload

    brand_name = payload.get("brand_name", params.brand)
    model_name = payload.get("model_name", params.model)

    groups: dict[str, list[FluidSearchResult]] = {}
    seen: set[tuple[str, str]] = set()

    for scored_point in search_result:
        p = scored_point.payload
        fluid_id_str = p.get("fluid_id")
        node_type = p.get("node_type", "ENGINE")
        dedup_key = (fluid_id_str, node_type)

        if not fluid_id_str or dedup_key in seen:
            continue
        seen.add(dedup_key)

        result = FluidSearchResult(
            fluid_id=UUID(fluid_id_str),
            canonical_name=p.get("fluid_canonical_name", ""),
            brand=p.get("fluid_brand"),
            product_line=p.get("fluid_product_line"),
            viscosity_sae=p.get("viscosity_sae"),
            api_class=p.get("api_class"),
            acea_class=p.get("acea_class"),
            oem_approvals=p.get("oem_approvals", []),
            fluid_type=p.get("fluid_type", "engine_oil"),
            volume_liters=p.get("volume_liters"),
            volume_with_filter=p.get("volume_with_filter"),
            is_oem_recommendation=p.get("is_oem_recommendation", False),
            confidence_score=scored_point.score,
            oem_specification=p.get("oem_specification"),
        )

        if node_type not in groups:
            groups[node_type] = []
        groups[node_type].append(result)

    node_groups = [
        NodeGroupResult(
            node_type=nt,
            node_label=NODE_LABELS.get(nt, nt),
            recommendations=recs,
        )
        for nt, recs in groups.items()
    ]

    if not node_groups:
        return None

    return SearchResponse(
        found_by="semantic",
        variant_id=None,
        brand=brand_name,
        model=model_name,
        engine_code=payload.get("engine_code"),
        engine_volume=payload.get("engine_volume"),
        groups=node_groups,
    )


# =============================================================
# Группировка по node_type
# =============================================================


def _group_by_node(recs: list[Recommendation]) -> list[NodeGroupResult]:
    groups: dict[str, list[FluidSearchResult]] = {}
    seen: set[tuple[UUID, str]] = set()

    for rec in recs:
        fluid = rec.fluid
        node_type = rec.node_type.value
        dedup_key = (fluid.id, node_type)

        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        result = FluidSearchResult(
            fluid_id=fluid.id,
            canonical_name=fluid.canonical_name,
            brand=fluid.brand,
            product_line=fluid.product_line,
            viscosity_sae=fluid.viscosity_sae,
            api_class=fluid.api_class,
            acea_class=fluid.acea_class,
            oem_approvals=fluid.oem_approvals or [],
            fluid_type=fluid.fluid_type.value,
            volume_liters=rec.volume_liters,
            volume_with_filter=rec.volume_with_filter,
            is_oem_recommendation=rec.is_oem_recommendation,
            confidence_score=rec.confidence_score,
            oem_specification=rec.oem_specification,
        )

        if node_type not in groups:
            groups[node_type] = []
        groups[node_type].append(result)

    return [
        NodeGroupResult(
            node_type=nt,
            node_label=NODE_LABELS.get(nt, nt),
            recommendations=recs,
        )
        for nt, recs in groups.items()
    ]


# =============================================================
# Главная функция — гибридный поиск
# =============================================================


async def find_recommendations(
    params: CarSearchSchema,
    tenant_id: UUID,
    db: AsyncSession,
    qdrant: AsyncQdrantClient,
) -> SearchResponse:
    result = await _search_exact_sql(params, tenant_id, db)
    if result:
        logger.info("Точный SQL-поиск успешен: %s %s", params.brand, params.model)
        return result

    logger.info("Точный поиск не дал результатов, пробуем Qdrant...")
    result = await _search_semantic_qdrant(params, tenant_id, qdrant)
    if result:
        logger.info("Семантический Qdrant-поиск успешен: %s %s", params.brand, params.model)
        return result

    raise NotFoundError(
        f"Не найдено рекомендаций для {params.brand} {params.model}"
    )


class NotFoundError(Exception):
    pass
