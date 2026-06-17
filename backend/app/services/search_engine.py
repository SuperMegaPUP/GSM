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
    ModelSearchInfo,
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
    """Ищет рекомендации гибким поиском по указанным параметрам.
    
    Если модель не указана — ищет по ВСЕМ моделям бренда.
    Если модель указана — ищет только по конкретной модели.
    """
    brand_stmt = select(CarBrand).where(CarBrand.company_id == tenant_id)
    if params.brand:
        brand_stmt = brand_stmt.where(CarBrand.name_ru.ilike(f"%{params.brand}%"))
    brand_result = await db.execute(brand_stmt)
    brand = brand_result.scalars().first()
    if not brand:
        return None

    # Собираем все подходящие модели
    model_stmt = select(CarModel).where(
        CarModel.company_id == tenant_id,
        CarModel.brand_id == brand.id,
    )
    if params.model:
        model_stmt = model_stmt.where(CarModel.name.ilike(f"%{params.model}%"))
    if params.year:
        model_stmt = model_stmt.where(
            (CarModel.year_start.is_(None) | (CarModel.year_start <= params.year)),
            (CarModel.year_end.is_(None) | (CarModel.year_end >= params.year)),
        )
    model_result = await db.execute(model_stmt)
    car_models = model_result.scalars().all()
    if not car_models:
        return None

    # Собираем все варианты для всех найденных моделей
    all_recs: list[Recommendation] = []
    for car_model in car_models:
        variant_stmt = select(CarVariant).where(
            CarVariant.company_id == tenant_id,
            CarVariant.model_id == car_model.id,
        )
        if params.engine_code:
            variant_stmt = variant_stmt.where(
                CarVariant.engine_code.ilike(f"%{params.engine_code}%")
            )
        if params.engine_volume:
            variant_stmt = variant_stmt.where(
                CarVariant.engine_volume == params.engine_volume
            )
        variant_result = await db.execute(variant_stmt)
        variants = variant_result.scalars().all()
        
        for variant in variants:
            rec_stmt = (
                select(Recommendation)
                .options(joinedload(Recommendation.fluid))
            .where(
                Recommendation.company_id == tenant_id,
                Recommendation.car_variant_id == variant.id,
            )
        )
        rec_result = await db.execute(rec_stmt)
        all_recs.extend(rec_result.unique().scalars().all())

    if not all_recs:
        return None

    groups = _group_by_node(all_recs)

    # Собираем информацию о всех найденных моделях
    models_info: list[ModelSearchInfo] = []
    for cm in car_models:
        variant_count_stmt = select(CarVariant).where(
            CarVariant.company_id == tenant_id,
            CarVariant.model_id == cm.id,
        )
        variant_count_result = await db.execute(variant_count_stmt)
        variant_count = len(variant_count_result.scalars().all())
        
        models_info.append(ModelSearchInfo(
            name=cm.name,
            engine_code=None,
            engine_volume=None,
            year_start=cm.year_start,
            year_end=cm.year_end,
            variants_count=variant_count,
        ))

    # Берём первую модель и первый вариант для отображения в заголовке
    first_model = car_models[0]
    first_variant_stmt = select(CarVariant).where(
        CarVariant.company_id == tenant_id,
        CarVariant.model_id == first_model.id,
    ).limit(1)
    first_variant_result = await db.execute(first_variant_stmt)
    first_variant = first_variant_result.scalars().first()

    return SearchResponse(
        found_by="exact_sql",
        variant_id=first_variant.id if first_variant else None,
        brand=brand.name_ru,
        model=first_model.name,
        engine_code=first_variant.engine_code if first_variant else None,
        engine_volume=first_variant.engine_volume if first_variant else None,
        year_start=first_model.year_start,
        year_end=first_model.year_end,
        groups=groups,
        models=models_info,
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
    if not query_text or query_text.strip() == "":
        logger.warning("Не удалось сформировать запрос для Qdrant")
        return None

    model = get_embedding_model()
    if model is None:
        logger.warning("Модель эмбеддингов недоступна — семантический поиск пропущен")
        return None
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
