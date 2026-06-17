import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Recommendation, NodeType
from app.services.normalizer import (
    FluidNormalizer,
    normalize_years,
    compute_variant_hash,
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


# =============================================================
# Атомарные UPSERT через сырой SQL
# =============================================================

async def _upsert_brand(
    db: AsyncSession,
    tenant_id: UUID,
    name_ru: str,
) -> UUID:
    result = await db.execute(
        text("""
            INSERT INTO car_brands (company_id, name_ru)
            VALUES (:tid, :name)
            ON CONFLICT (company_id, name_ru) DO UPDATE SET updated_at = NOW()
            RETURNING id
        """),
        {"tid": str(tenant_id), "name": name_ru},
    )
    return result.scalar_one()


async def _upsert_model(
    db: AsyncSession,
    tenant_id: UUID,
    brand_id: UUID,
    name: str,
    generation: Optional[str] = None,
) -> UUID:
    result = await db.execute(
        text("""
            INSERT INTO car_models (company_id, brand_id, name, generation)
            VALUES (:tid, :bid, :name, :gen)
            ON CONFLICT (company_id, brand_id, name, generation) DO UPDATE SET updated_at = NOW()
            RETURNING id
        """),
        {"tid": str(tenant_id), "bid": str(brand_id), "name": name, "gen": generation},
    )
    return result.scalar_one()


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
) -> UUID:
    result = await db.execute(
        text("""
            INSERT INTO car_variants 
                (company_id, model_id, engine_code, engine_volume, body_type,
                 year_start, year_end, source_hash)
            VALUES (:tid, :mid, :ec, :ev, :bt, :ys, :ye, :sh)
            ON CONFLICT (source_hash) DO UPDATE SET
                model_id = EXCLUDED.model_id,
                engine_code = EXCLUDED.engine_code,
                engine_volume = EXCLUDED.engine_volume,
                body_type = EXCLUDED.body_type,
                year_start = EXCLUDED.year_start,
                year_end = EXCLUDED.year_end,
                updated_at = NOW()
            RETURNING id
        """),
        {
            "tid": str(tenant_id),
            "mid": str(model_id),
            "ec": engine_code,
            "ev": engine_volume,
            "bt": body_type,
            "ys": year_start,
            "ye": year_end,
            "sh": source_hash,
        },
    )
    return result.scalar_one()


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
) -> UUID:
    result = await db.execute(
        text("""
            INSERT INTO fluids 
                (company_id, canonical_name, brand, product_line, viscosity_sae,
                 api_class, fluid_type, hash_signature)
            VALUES (:tid, :cn, :br, :pl, :vs, :ac, :ft, :hs)
            ON CONFLICT (company_id, hash_signature) DO UPDATE SET
                canonical_name = EXCLUDED.canonical_name,
                brand = EXCLUDED.brand,
                product_line = EXCLUDED.product_line,
                viscosity_sae = EXCLUDED.viscosity_sae,
                api_class = EXCLUDED.api_class,
                fluid_type = EXCLUDED.fluid_type,
                updated_at = NOW()
            RETURNING id
        """),
        {
            "tid": str(tenant_id),
            "cn": canonical_name,
            "br": brand,
            "pl": product_line,
            "vs": viscosity_sae,
            "ac": api_class,
            "ft": fluid_type,
            "hs": hash_signature,
        },
    )
    return result.scalar_one()


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
        if i > 0 and i % 5000 == 0:
            logger.info("ETL progress: %d/%d rows", i, total)
        brand_name = (row_data.get("brand") or "").strip()
        model_name = (row_data.get("model") or "").strip()
        engine_code = row_data.get("engine") or None
        body_type = row_data.get("body") or None
        engine_volume_str = row_data.get("engine_volume") or None
        engine_volume = _parse_float(engine_volume_str)
        year_start, year_end = normalize_years(row_data.get("years"))
        fluid_name = row_data.get("fluid_name") or None
        viscosity = row_data.get("viscosity") or None
        api_class = row_data.get("api_class") or None
        node_type = row_data.get("node_type") or None
        volume = _parse_float(row_data.get("volume"))
        volume_with_filter = _parse_float(row_data.get("volume_with_filter"))

        try:
            if not brand_name:
                raise ValueError("Пустое название бренда")
            if not model_name:
                raise ValueError("Пустое название модели")

            # --- Brand UPSERT в отдельном savepoint ---
            brand_id: UUID
            if brand_name in brand_cache:
                brand_id = brand_cache[brand_name]
            else:
                async with db.begin_nested():
                    brand_id = await _upsert_brand(db, tenant_id, brand_name)
                brand_cache[brand_name] = brand_id
                created_brands += 1

            # --- Model UPSERT в отдельном savepoint ---
            model_id: UUID
            cache_key = (brand_id, model_name)
            if cache_key in model_cache:
                model_id = model_cache[cache_key]
            else:
                async with db.begin_nested():
                    model_id = await _upsert_model(
                        db, tenant_id, brand_id, model_name,
                    )
                model_cache[cache_key] = model_id
                created_models += 1

            # --- Variant UPSERT в отдельном savepoint ---
            variant_id: UUID
            source_hash = compute_variant_hash(
                str(model_id), engine_code, body_type, engine_volume_str,
            )
            if source_hash in variant_cache:
                variant_id = variant_cache[source_hash]
            else:
                async with db.begin_nested():
                    variant_id = await _upsert_variant(
                        db, tenant_id, model_id,
                        engine_code=engine_code,
                        engine_volume=engine_volume,
                        body_type=body_type,
                        year_start=year_start,
                        year_end=year_end,
                        source_hash=source_hash,
                    )
                variant_cache[source_hash] = variant_id
                created_variants += 1

            # --- Fluid UPSERT в отдельном savepoint ---
            fluid_id: UUID
            normalized = FluidNormalizer.normalize(
                fluid_name, viscosity, api_class, node_type,
            )
            hash_sig = normalized["hash_signature"]
            if hash_sig in fluid_cache:
                fluid_id = fluid_cache[hash_sig]
            else:
                async with db.begin_nested():
                    fluid_id = await _upsert_fluid(
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
                created_fluids += 1

            # --- Recommendation INSERT в отдельном savepoint ---
            try:
                nt = NodeType(node_type) if node_type else NodeType.ENGINE
            except ValueError:
                nt = NodeType.ENGINE

            async with db.begin_nested():
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
            # begin_nested() автоматически откатывает savepoint при исключении.
            # НЕ вызываем db.rollback() — он ломает всю сессию!

        # Коммит каждые BATCH_SIZE строк
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
