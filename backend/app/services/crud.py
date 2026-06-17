import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CarBrand, CarModel, CarVariant, Fluid
from app.schemas.catalog_schemas import (
    CarBrandCreate,
    CarBrandUpdate,
    CarModelCreate,
    CarVariantCreate,
    FluidCreate,
    FluidUpdate,
)


# =============================================================
# CarBrand
# =============================================================

async def list_brands(
    db: AsyncSession,
    tenant_id: UUID,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
) -> tuple[list[CarBrand], int]:
    query = select(CarBrand).where(CarBrand.company_id == tenant_id)
    count_query = select(func.count(CarBrand.id)).where(
        CarBrand.company_id == tenant_id
    )

    if search:
        pattern = f"%{search}%"
        query = query.where(CarBrand.name_ru.ilike(pattern))
        count_query = count_query.where(CarBrand.name_ru.ilike(pattern))

    query = query.order_by(CarBrand.name_ru).offset(offset).limit(limit)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def create_brand(
    db: AsyncSession,
    tenant_id: UUID,
    data: CarBrandCreate,
) -> CarBrand:
    existing = await db.execute(
        select(CarBrand).where(
            CarBrand.company_id == tenant_id,
            CarBrand.name_ru == data.name_ru,
        )
    )
    if existing.scalar_one_or_none():
        raise DuplicateError(f"Марка '{data.name_ru}' уже существует")

    brand = CarBrand(
        company_id=tenant_id,
        name_ru=data.name_ru,
        name_en=data.name_en,
        country=data.country,
    )
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return brand


async def get_brand(
    db: AsyncSession,
    tenant_id: UUID,
    brand_id: UUID,
) -> Optional[CarBrand]:
    result = await db.execute(
        select(CarBrand).where(
            CarBrand.company_id == tenant_id,
            CarBrand.id == brand_id,
        )
    )
    return result.scalar_one_or_none()


async def update_brand(
    db: AsyncSession,
    tenant_id: UUID,
    brand_id: UUID,
    data: CarBrandUpdate,
) -> CarBrand:
    brand = await get_brand(db, tenant_id, brand_id)
    if brand is None:
        raise NotFoundError("Марка не найдена")

    if data.name_ru is not None:
        existing = await db.execute(
            select(CarBrand).where(
                CarBrand.company_id == tenant_id,
                CarBrand.name_ru == data.name_ru,
                CarBrand.id != brand_id,
            )
        )
        if existing.scalar_one_or_none():
            raise DuplicateError(f"Марка '{data.name_ru}' уже существует")
        brand.name_ru = data.name_ru

    if data.name_en is not None:
        brand.name_en = data.name_en
    if data.country is not None:
        brand.country = data.country

    await db.commit()
    await db.refresh(brand)
    return brand


# =============================================================
# CarModel
# =============================================================

async def list_models(
    db: AsyncSession,
    tenant_id: UUID,
    brand_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
) -> tuple[list[CarModel], int]:
    query = select(CarModel).where(CarModel.company_id == tenant_id)
    count_query = select(func.count(CarModel.id)).where(
        CarModel.company_id == tenant_id
    )

    if brand_id:
        query = query.where(CarModel.brand_id == brand_id)
        count_query = count_query.where(CarModel.brand_id == brand_id)

    if search:
        pattern = f"%{search}%"
        query = query.where(CarModel.name.ilike(pattern))
        count_query = count_query.where(CarModel.name.ilike(pattern))

    query = query.order_by(CarModel.name).offset(offset).limit(limit)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def create_model(
    db: AsyncSession,
    tenant_id: UUID,
    data: CarModelCreate,
) -> CarModel:
    existing = await db.execute(
        select(CarModel).where(
            CarModel.company_id == tenant_id,
            CarModel.brand_id == data.brand_id,
            CarModel.name == data.name,
        )
    )
    if existing.scalar_one_or_none():
        raise DuplicateError(
            f"Модель '{data.name}' уже существует для этого бренда"
        )

    model = CarModel(
        company_id=tenant_id,
        brand_id=data.brand_id,
        name=data.name,
        generation=data.generation,
        year_start=data.year_start,
        year_end=data.year_end,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


# =============================================================
# CarVariant
# =============================================================

async def list_variants(
    db: AsyncSession,
    tenant_id: UUID,
    model_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CarVariant], int]:
    query = select(CarVariant).where(CarVariant.company_id == tenant_id)
    count_query = select(func.count(CarVariant.id)).where(
        CarVariant.company_id == tenant_id
    )

    if model_id:
        query = query.where(CarVariant.model_id == model_id)
        count_query = count_query.where(CarVariant.model_id == model_id)

    query = query.order_by(
        CarVariant.year_start, CarVariant.engine_code
    ).offset(offset).limit(limit)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def create_variant(
    db: AsyncSession,
    tenant_id: UUID,
    data: CarVariantCreate,
) -> CarVariant:
    variant = CarVariant(
        company_id=tenant_id,
        model_id=data.model_id,
        engine_code=data.engine_code,
        engine_volume=data.engine_volume,
        fuel_type=data.fuel_type,
        body_type=data.body_type,
        drive_type=data.drive_type,
        transmission_type=data.transmission_type,
        year_start=data.year_start,
        year_end=data.year_end,
    )
    db.add(variant)
    await db.commit()
    await db.refresh(variant)
    return variant


# =============================================================
# Fluid
# =============================================================

async def list_fluids(
    db: AsyncSession,
    tenant_id: UUID,
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    fluid_type: Optional[str] = None,
) -> tuple[list[Fluid], int]:
    query = select(Fluid).where(Fluid.company_id == tenant_id)
    count_query = select(func.count(Fluid.id)).where(
        Fluid.company_id == tenant_id
    )

    if search:
        pattern = f"%{search}%"
        query = query.where(Fluid.canonical_name.ilike(pattern))
        count_query = count_query.where(Fluid.canonical_name.ilike(pattern))

    if fluid_type:
        query = query.where(Fluid.fluid_type == fluid_type)
        count_query = count_query.where(Fluid.fluid_type == fluid_type)

    query = query.order_by(Fluid.canonical_name).offset(offset).limit(limit)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def create_fluid(
    db: AsyncSession,
    tenant_id: UUID,
    data: FluidCreate,
) -> Fluid:
    existing = await db.execute(
        select(Fluid).where(
            Fluid.company_id == tenant_id,
            Fluid.canonical_name == data.canonical_name,
        )
    )
    if existing.scalar_one_or_none():
        raise DuplicateError(
            f"Жидкость '{data.canonical_name}' уже существует"
        )

    fluid = Fluid(
        company_id=tenant_id,
        canonical_name=data.canonical_name,
        brand=data.brand,
        product_line=data.product_line,
        viscosity_sae=data.viscosity_sae,
        api_class=data.api_class,
        acea_class=data.acea_class,
        oem_approvals=data.oem_approvals,
        fluid_type=data.fluid_type,
    )
    db.add(fluid)
    await db.commit()
    await db.refresh(fluid)
    return fluid


async def get_fluid(
    db: AsyncSession,
    tenant_id: UUID,
    fluid_id: UUID,
) -> Optional[Fluid]:
    result = await db.execute(
        select(Fluid).where(
            Fluid.company_id == tenant_id,
            Fluid.id == fluid_id,
        )
    )
    return result.scalar_one_or_none()


# =============================================================
# Кастомные исключения
# =============================================================

class DuplicateError(Exception):
    pass


class NotFoundError(Exception):
    pass
