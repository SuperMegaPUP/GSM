from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_active_user
from app.models.analytics import DailyActionPlan
from app.models.models import User
from app.schemas.analytics_schemas import ActionItem, DailyActionPlanResponse
from app.services.predictive_analytics import generate_daily_action_plan

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/daily-plan", response_model=DailyActionPlanResponse)
async def get_daily_plan(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
    force: bool = Query(False, description="Принудительно перегенерировать план"),
):
    today = date.today()

    # Если force=true — удаляем сегодняшний кеш и генерируем заново
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
