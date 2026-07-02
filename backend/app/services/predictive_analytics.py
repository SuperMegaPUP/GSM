import logging
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import DailyActionPlan
from app.models.models import (
    CarBrand, CarModel, CarVariant, Fluid, ImportBatch, Recommendation,
)
from app.schemas.analytics_schemas import ActionItem

logger = logging.getLogger(__name__)

OBJECTION_CATEGORIES = [
    "price", "quality", "logistics", "service",
    "brand", "business", "closing", "storage", "harmful",
]


async def generate_daily_action_plan(
    company_id: UUID,
    db: AsyncSession,
) -> list[ActionItem]:
    items: list[ActionItem] = []
    today = date.today()

    # ── Правило 1: последний импорт ──────────────────────────────
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

    # ── Правило 2: количество уникальных масел ───────────────────
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

    # ── Правило 3: покрытие брендов ───────────────────────────────
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
            message=f"Добавьте каталоги новых брендов (сейчас покрыто {brand_count})",
        ))

    # ── Правило 4: скользкие кейсы (частые неудачи) ──────────────
    result = await db.execute(
        select(
            func.count(text("*")),
            func.array_agg(text("id")),
        )
        .select_from(text("objection_cases"))
        .where(text(
            "is_published = true AND usage_count > 5 "
            "AND failure_count::numeric / NULLIF(usage_count, 0) > 0.4"
        ))
    )
    row = result.one()
    troubled_count = row[0] or 0
    if troubled_count > 0:
        troubled_ids = row[1] or []
        items.append(ActionItem(
            type="troubled_cases",
            severity="warning",
            message=(
                f"{troubled_count} кейс(ов) с высокой частотой неудач "
                f"(>40%): {', '.join(str(i) for i in (troubled_ids or [])[:5])}"
                f"{'…' if len(troubled_ids or []) > 5 else ''}"
            ),
        ))

    # ── Правило 5: успешные паттерны (золотые кейсы) ─────────────
    result = await db.execute(
        select(
            func.count(text("*")),
            func.array_agg(text("id")),
        )
        .select_from(text("objection_cases"))
        .where(text(
            "is_published = true AND usage_count > 10 "
            "AND success_count::numeric / NULLIF(usage_count, 0) > 0.8"
        ))
    )
    row = result.one()
    golden_count = row[0] or 0
    if golden_count > 0:
        golden_ids = row[1] or []
        items.append(ActionItem(
            type="golden_cases",
            severity="info",
            message=(
                f"{golden_count} кейс(ов) с success rate >80% "
                f"(«золотой стандарт»): {', '.join(str(i) for i in (golden_ids or [])[:5])}"
                f"{'…' if len(golden_ids or []) > 5 else ''}"
            ),
        ))

    # ── Правило 6: популярные возражения (по sales_interactions) ─
    result = await db.execute(
        select(
            text("category"),
            func.count(text("*")).label("cnt"),
        )
        .select_from(text("sales_interactions"))
        .where(text("category IS NOT NULL"))
        .group_by(text("category"))
        .order_by(text("cnt DESC"))
        .limit(5)
    )
    top_categories = result.all()
    if top_categories:
        cat_list = ", ".join(
            f"{r.category} ({r.cnt})" for r in top_categories
        )
        items.append(ActionItem(
            type="popular_objections",
            severity="info",
            message=f"Топ возражений: {cat_list}",
        ))

    # ── Правило 7: пустые категории (нет ни одного кейса) ────────
    result = await db.execute(
        select(func.distinct(text("category")))
        .select_from(text("objection_cases"))
    )
    present_cats = {r[0] for r in result.all()}
    empty_cats = [c for c in OBJECTION_CATEGORIES if c not in present_cats]
    if empty_cats:
        items.append(ActionItem(
            type="empty_categories",
            severity="info",
            message=f"Добавьте кейсы для категорий: {', '.join(empty_cats)}",
        ))

    # ── Сохраняем план ──────────────────────────────────────────
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
