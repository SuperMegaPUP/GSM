import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    CarBrand,
    CarModel,
    CarVariant,
    Fluid,
    Recommendation,
    NodeType,
)
from app.services.normalizer import (
    FluidNormalizer,
    normalize_years,
    compute_variant_hash,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 200


# =============================================================
# Вспомогательные UPSERT-функции
# =============================================================

async def _upsert_brand(
    db: AsyncSession,
    tenant_id: UUID,
    name_ru: str,
) -> tuple[UUID, bool]:
    stmt = (
        pg_insert(CarBrand)
        .values(
            company_id=tenant_id,
            name_ru=name_ru,
        )
        .on_conflict_do_nothing(index_elements=["name_ru", "company_id"])
        .returning(CarBrand.id)
    )
    result = await db.execute(stmt)
    row = result.fetchone()
    if row:
        return row[0], True

    existing = await db.execute(
        select(CarBrand.id).where(
            CarBrand.company_id == tenant_id,
            CarBrand.name_ru == name_ru,
        )
    )
    existing_id = existing.scalar_one()
    return existing_id, False


async def _upsert_model(
    db: AsyncSession,
    tenant_id: UUID,
    brand_id: UUID,
    name: str,
    generation: Optional[str] = None,
) -> tuple[UUID, bool]:
    stmt = (
        pg_insert(CarModel)
        .values(
            company_id=tenant_id,
            brand_id=brand_id,
            name=name,
            generation=generation,
        )
        .on_conflict_do_nothing(
            index_elements=["brand_id", "name", "generation", "company_id"]
        )
        .returning(CarModel.id)
    )
    result = await db.execute(stmt)
    row = result.fetchone()
    if row:
        return row[0], True

    existing = await db.execute(
        select(CarModel.id).where(
            CarModel.company_id == tenant_id,
            CarModel.brand_id == brand_id,
            CarModel.name == name,
            (
                (CarModel.generation == generation)
                if generation
                else CarModel.generation.is_(None)
            ),
        )
    )
    existing_id = existing.scalar_one()
    return existing_id, False


async def _upsert_variant(
    db: AsyncSession,
    tenant_id: UUID,
    model_id: UUID,
    engine_code: Optional[str],
    engine_volume: Optional[float],
    body_type: Optional[str],
    year_start: Optional[int],
    year_end: Optional[int],
    source_hash: str,
) -> tuple[UUID, bool]:
    stmt = (
        pg_insert(CarVariant)
        .values(
            company_id=tenant_id,
            model_id=model_id,
            engine_code=engine_code,
            engine_volume=engine_volume,
            body_type=body_type,
            year_start=year_start,
            year_end=year_end,
            source_hash=source_hash,
        )
        .on_conflict_do_nothing(index_elements=["source_hash"])
        .returning(CarVariant.id)
    )
    result = await db.execute(stmt)
    row = result.fetchone()
    if row:
        return row[0], True

    existing = await db.execute(
        select(CarVariant.id).where(
            CarVariant.company_id == tenant_id,
            CarVariant.source_hash == source_hash,
        )
    )
    existing_id = existing.scalar_one()
    return existing_id, False


async def _upsert_fluid(
    db: AsyncSession,
    tenant_id: UUID,
    canonical_name: str,
    brand: Optional[str],
    product_line: Optional[str],
    viscosity_sae: Optional[str],
    api_class: Optional[str],
    fluid_type: str,
    hash_signature: str,
) -> tuple[UUID, bool]:
    stmt = (
        pg_insert(Fluid)
        .values(
            company_id=tenant_id,
            canonical_name=canonical_name,
            brand=brand,
            product_line=product_line,
            viscosity_sae=viscosity_sae,
            api_class=api_class,
            fluid_type=fluid_type,
            hash_signature=hash_signature,
        )
        .on_conflict_do_nothing(index_elements=["hash_signature"])
        .returning(Fluid.id)
    )
    result = await db.execute(stmt)
    row = result.fetchone()
    if row:
        return row[0], True

    existing = await db.execute(
        select(Fluid.id).where(
            Fluid.company_id == tenant_id,
            Fluid.hash_signature == hash_signature,
        )
    )
    existing_id = existing.scalar_one()
    return existing_id, False


# =============================================================
# Основная функция обработки импорта
# =============================================================

async def process_import_batch(
    batch_id: UUID,
    raw_rows: list[dict],
    tenant_id: UUID,
    db: AsyncSession,
) -> dict:
    total = len(raw_rows)
    success = 0
    errors = 0
    created_brands = 0
    created_models = 0
    created_variants = 0
    created_fluids = 0

    brand_cache: dict[str, UUID] = {}
    model_cache: dict[tuple[UUID, str], UUID] = {}
    variant_cache: dict[str, UUID] = {}
    fluid_cache: dict[str, UUID] = {}

    for i, row_data in enumerate(raw_rows):
        try:
            async with db.begin_nested():
                brand_name = (row_data.get("brand") or "").strip()
                if not brand_name:
                    raise ValueError("Пустое название бренда")

                if brand_name not in brand_cache:
                    brand_id, is_new = await _upsert_brand(db, tenant_id, brand_name)
                    brand_cache[brand_name] = brand_id
                    if is_new:
                        created_brands += 1
                brand_id = brand_cache[brand_name]

                model_name = (row_data.get("model") or "").strip()
                if not model_name:
                    raise ValueError("Пустое название модели")

                cache_key = (brand_id, model_name)
                if cache_key not in model_cache:
                    model_id, is_new = await _upsert_model(
                        db, tenant_id, brand_id, model_name,
                    )
                    model_cache[cache_key] = model_id
                    if is_new:
                        created_models += 1
                model_id = model_cache[cache_key]

                engine_code = row_data.get("engine") or None
                body_type = row_data.get("body") or None
                engine_volume_str = row_data.get("engine_volume") or None
                engine_volume = _parse_float(engine_volume_str)
                year_start, year_end = normalize_years(row_data.get("years"))
                source_hash = compute_variant_hash(
                    str(model_id), engine_code, body_type, engine_volume_str,
                )

                if source_hash not in variant_cache:
                    variant_id, is_new = await _upsert_variant(
                        db, tenant_id, model_id,
                        engine_code=engine_code,
                        engine_volume=engine_volume,
                        body_type=body_type,
                        year_start=year_start,
                        year_end=year_end,
                        source_hash=source_hash,
                    )
                    variant_cache[source_hash] = variant_id
                    if is_new:
                        created_variants += 1
                variant_id = variant_cache[source_hash]

                fluid_name = row_data.get("fluid_name") or None
                viscosity = row_data.get("viscosity") or None
                api_class = row_data.get("api_class") or None
                node_type = row_data.get("node_type") or None

                normalized = FluidNormalizer.normalize(
                    fluid_name, viscosity, api_class, node_type,
                )
                hash_sig = normalized["hash_signature"]

                if hash_sig not in fluid_cache:
                    fluid_id, is_new = await _upsert_fluid(
                        db, tenant_id,
                        canonical_name=normalized["canonical_name"],
                        brand=normalized["brand"],
                        product_line=normalized["product_line"],
                        viscosity_sae=normalized["viscosity_sae"],
                        api_class=normalized["api_class"],
                        fluid_type=normalized["fluid_type"].value,
                        hash_signature=hash_sig,
                    )
                    fluid_cache[hash_sig] = fluid_id
                    if is_new:
                        created_fluids += 1
                fluid_id = fluid_cache[hash_sig]

                volume = _parse_float(row_data.get("volume"))
                volume_with_filter = _parse_float(row_data.get("volume_with_filter"))

                try:
                    nt = NodeType(node_type) if node_type else NodeType.ENGINE
                except ValueError:
                    nt = NodeType.ENGINE

                db.add(Recommendation(
                    company_id=tenant_id,
                    car_variant_id=variant_id,
                    node_type=nt,
                    fluid_id=fluid_id,
                    volume_liters=volume,
                    volume_with_filter=volume_with_filter,
                    is_oem_recommendation=True,
                    source="excel_import",
                ))
            success += 1
        except Exception as exc:
            errors += 1
            logger.warning(
                "Ошибка строки %d batch=%s: %s", i, batch_id, exc, exc_info=True
            )

        if i > 0 and i % BATCH_SIZE == 0:
            await db.commit()
            logger.info(
                "Обработано %d / %d строк batch=%s", i, total, batch_id
            )

    await db.commit()

    return {
        "total": total,
        "success": success,
        "errors": errors,
        "created_brands": created_brands,
        "created_models": created_models,
        "created_variants": created_variants,
        "created_fluids": created_fluids,
    }


def _parse_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return None
