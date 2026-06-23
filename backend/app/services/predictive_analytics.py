import logging
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import DailyActionPlan
from app.models.models import (
    CarBrand, CarModel, CarVariant, Fluid, ImportBatch, Recommendation,
)
from app.schemas.analytics_schemas import ActionItem

logger = logging.getLogger(__name__)


async def generate_daily_action_plan(
    company_id: UUID,
    db: AsyncSession,
) -> list[ActionItem]:
    items: list[ActionItem] = []
    today = date.today()

    # Правило 1: последний импорт
    result = await db.execute(
        select(func.max(ImportBatch.created_at))
        .where(ImportBatch.company_id == company_id)
        .where(ImportBatch.status == "completed")
    )
    last_import = result.scalar()
    if last_import is None:
        items.append(ActionItem(
            type="import",
            severity="high",
            message="Загрузите первый каталог масел — база пуста",
        ))
    elif (datetime.now(timezone.utc) - last_import).days > 30:
        items.append(ActionItem(
            type="import",
            severity="warning",
            message=(
                f"Загрузите свежий каталог (последний: "
                f"{last_import.strftime('%d.%m.%Y')}, "
                f"{(datetime.now(timezone.utc) - last_import).days} дней назад)"
            ),
        ))

    # Правило 2: количество уникальных масел
    result = await db.execute(
        select(func.count(Fluid.id))
        .where(Fluid.company_id == company_id)
    )
    fluid_count = result.scalar() or 0
    if fluid_count < 50:
        items.append(ActionItem(
            type="fluids",
            severity="info",
            message=f"Расширьте ассортимент масел (сейчас: {fluid_count})",
        ))

    # Правило 3: покрытие брендов (через рекомендации → варианты → модели → бренды)
    result = await db.execute(
        select(func.count(func.distinct(CarBrand.id)))
        .select_from(Recommendation)
        .join(Recommendation.car_variant)
        .join(CarVariant.model)
        .join(CarModel.brand)
        .where(Recommendation.company_id == company_id)
    )
    brand_count = result.scalar() or 0
    if brand_count < 10:
        items.append(ActionItem(
            type="brands",
            severity="info",
            message=(
                f"Добавьте каталоги новых брендов "
                f"(сейчас покрыто {brand_count})"
            ),
        ))

    # Сохраняем план
    existing = await db.execute(
        select(DailyActionPlan).where(
            DailyActionPlan.company_id == company_id,
            DailyActionPlan.plan_date == today,
        )
    )
    plan = existing.scalar_one_or_none()

    if plan:
        plan.items = [item.model_dump() for item in items]
    else:
        plan = DailyActionPlan(
            company_id=company_id,
            plan_date=today,
            items=[item.model_dump() for item in items],
        )
        db.add(plan)

    await db.commit()
    return items
