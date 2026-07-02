from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_active_user
from app.models.analytics import DailyActionPlan
from app.models.models import User
from app.schemas.analytics_schemas import (
    ActionItem,
    CaseHistoryItem,
    CaseHistoryResponse,
    DailyActionPlanResponse,
    InsightItem,
    InsightsResponse,
    TrendPoint,
    TrendsResponse,
)
from app.services.predictive_analytics import generate_daily_action_plan

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/daily-plan", response_model=DailyActionPlanResponse)
async def get_daily_plan(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    force: bool = Query(False, description="Принудительно перегенерировать план"),
):
    today = date.today()

    if force:
        existing = await session.execute(
            select(DailyActionPlan).where(
                DailyActionPlan.company_id == current_user.company_id,
                DailyActionPlan.plan_date == today,
            )
        )
        plan = existing.scalar_one_or_none()
        if plan:
            await session.delete(plan)
            await session.commit()

    result = await session.execute(
        select(DailyActionPlan).where(
            DailyActionPlan.company_id == current_user.company_id,
            DailyActionPlan.plan_date == today,
        )
    )
    plan = result.scalar_one_or_none()

    if plan is None:
        await generate_daily_action_plan(
            current_user.company_id, session,
        )
        result = await session.execute(
            select(DailyActionPlan).where(
                DailyActionPlan.company_id == current_user.company_id,
                DailyActionPlan.plan_date == today,
            )
        )
        plan = result.scalar_one_or_none()

    if plan is None:
        return DailyActionPlanResponse(
            id="00000000-0000-0000-0000-000000000000",
            company_id=current_user.company_id,
            plan_date=today,
            items=[],
        )

    return DailyActionPlanResponse(
        id=plan.id,
        company_id=plan.company_id,
        plan_date=plan.plan_date,
        items=[ActionItem(**item) for item in (plan.items or [])],
    )


@router.get("/trends", response_model=TrendsResponse)
async def get_trends(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    days: int = Query(30, description="Глубина в днях"),
):
    start_date = (datetime.now() - timedelta(days=days)).date()
    today = date.today()

    # Historical data from daily_trends (past dates only)
    result = await session.execute(
        select(
            text("date, metric, value")
        )
        .select_from(text("daily_trends"))
        .where(text("company_id = :cid AND date >= :start AND date < :today"))
        .order_by(text("metric, date"))
        .params(cid=current_user.company_id, start=start_date, today=today)
    )

    by_metric: dict[str, list[TrendPoint]] = {}
    for row in result.all():
        by_metric.setdefault(row.metric, []).append(
            TrendPoint(date=str(row.date), value=row.value)
        )

    # ── Live data for today ────────────────────────────────────
    cid = current_user.company_id

    # objections_total
    cnt = await session.scalar(
        select(func.count(text("*")))
        .select_from(text("sales_interactions"))
        .where(text("tenant_id = :cid AND created_at::date = :today"))
        .params(cid=cid, today=today)
    )
    by_metric.setdefault("objections_total", []).append(
        TrendPoint(date=str(today), value={"count": cnt or 0})
    )

    # objections_by_category
    cat_rows = await session.execute(
        select(
            text("COALESCE(category, 'unknown') AS cat"),
            func.count(text("*")).label("cnt"),
        )
        .select_from(text("sales_interactions"))
        .where(text("tenant_id = :cid AND created_at::date = :today"))
        .group_by(text("cat"))
        .params(cid=cid, today=today)
    )
    cat_data = {r.cat: r.cnt for r in cat_rows.all()}
    by_metric.setdefault("objections_by_category", []).append(
        TrendPoint(date=str(today), value=cat_data)
    )

    # case_stats
    case_row = await session.execute(
        select(
            func.coalesce(func.sum(text("usage_count")), 0).label("total_used"),
            func.coalesce(func.sum(text("success_count")), 0).label("total_won"),
            func.coalesce(func.sum(text("failure_count")), 0).label("total_lost"),
            func.count(text("*")).label("total_cases"),
        )
        .select_from(text("objection_cases"))
        .where(text("is_published = true"))
    )
    cr = case_row.one()
    by_metric.setdefault("case_stats", []).append(
        TrendPoint(
            date=str(today),
            value={
                "total_used": cr.total_used,
                "total_won": cr.total_won,
                "total_lost": cr.total_lost,
                "total_cases": cr.total_cases,
                "success_rate": round(
                    cr.total_won / (cr.total_won + cr.total_lost or 1), 3
                ),
            },
        )
    )

    return TrendsResponse(
        objections_total=by_metric.get("objections_total", []),
        objections_by_category=by_metric.get("objections_by_category", []),
        case_stats=by_metric.get("case_stats", []),
    )


@router.get("/insights", response_model=InsightsResponse)
async def get_insights(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    insights: list[InsightItem] = []

    # Insight 1: проблемные кейсы
    result = await session.execute(
        select(
            text("id, category_label, objection_text, usage_count, success_count, failure_count")
        )
        .select_from(text("objection_cases"))
        .where(text(
            "is_published = true AND usage_count > 5 "
            "AND failure_count::numeric / NULLIF(usage_count, 0) > 0.4"
        ))
        .order_by(text("failure_count DESC"))
        .limit(3)
    )
    for row in result.all():
        insights.append(InsightItem(
            type="troubled_case",
            severity="warning",
            message=f"Кейс «{row.objection_text[:60]}…» — {row.failure_count} неудач из {row.usage_count} использований",
        ))

    # Insight 2: золотые кейсы
    result = await session.execute(
        select(
            text("id, category_label, objection_text, usage_count, success_count, failure_count")
        )
        .select_from(text("objection_cases"))
        .where(text(
            "is_published = true AND usage_count > 10 "
            "AND success_count::numeric / NULLIF(usage_count, 0) > 0.8"
        ))
        .order_by(text("success_count DESC"))
        .limit(3)
    )
    for row in result.all():
        insights.append(InsightItem(
            type="golden_case",
            severity="info",
            message=f"«Золотой стандарт»: кейс «{row.objection_text[:60]}…» — {row.success_count} успехов из {row.usage_count}",
        ))

    # Insight 3: пустые категории
    result = await session.execute(
        select(func.distinct(text("category")))
        .select_from(text("objection_cases"))
    )
    present_cats = {r[0] for r in result.all()}
    ALL_CATS = ["price", "quality", "logistics", "service", "brand", "business", "closing", "storage", "harmful"]
    empty_cats = [c for c in ALL_CATS if c not in present_cats]
    if empty_cats:
        insights.append(InsightItem(
            type="empty_category",
            severity="info",
            message=f"Пополните категории: {', '.join(empty_cats)}",
        ))

    # Insight 4: популярные возражения
    result = await session.execute(
        select(
            text("COALESCE(category, 'unknown') AS cat"),
            func.count(text("*")).label("cnt"),
        )
        .select_from(text("sales_interactions"))
        .where(text("category IS NOT NULL"))
        .group_by(text("cat"))
        .order_by(text("cnt DESC"))
        .limit(3)
    )
    top = result.all()
    if top:
        cat_list = ", ".join(f"{r.cat} ({r.cnt})" for r in top)
        insights.append(InsightItem(
            type="popular_objections",
            severity="info",
            message=f"Чаще всего возражают про: {cat_list}",
        ))

    return InsightsResponse(insights=insights)


@router.get("/cases/{case_id}/history", response_model=CaseHistoryResponse)
async def get_case_history(
    case_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(20, description="Максимум записей истории"),
):
    # Получаем статистику кейса
    result = await session.execute(
        select(
            text("usage_count, success_count, failure_count, objection_text")
        )
        .select_from(text("objection_cases"))
        .where(text("id = :cid"))
        .params(cid=case_id)
    )
    case = result.one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Кейс не найден")

    total = case.usage_count or 1
    success_rate = round(case.success_count / total, 3)

    # История взаимодействий (из sales_interactions, где этот кейс был в retrieved_case_ids)
    result = await session.execute(
        select(
            text("id, objection, category, created_at"),
        )
        .select_from(text("sales_interactions"))
        .where(text(":cid = ANY(retrieved_case_ids)"))
        .order_by(text("created_at DESC"))
        .limit(limit)
        .params(cid=case_id)
    )
    history = [
        CaseHistoryItem(
            interaction_id=r.id,
            objection=r.objection,
            category=r.category,
            created_at=str(r.created_at),
            outcome=None,
        )
        for r in result.all()
    ]

    return CaseHistoryResponse(
        case_id=case_id,
        usage_count=case.usage_count,
        success_count=case.success_count,
        failure_count=case.failure_count,
        success_rate=success_rate,
        history=history,
    )
