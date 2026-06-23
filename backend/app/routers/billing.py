from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_active_user
from app.models.models import User
from app.models.subscription import Subscription, SubscriptionStatus
from app.schemas.billing_schemas import (
    ActivateSubscriptionRequest,
    SubscriptionResponse,
)
from app.services.billing_service import activate_subscription, get_subscription

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _build_response(sub: Subscription) -> SubscriptionResponse:
    now = datetime.now(timezone.utc)
    days_left = None
    if sub.status == SubscriptionStatus.ACTIVE:
        end = sub.end_date.replace(tzinfo=timezone.utc)
        days_left = max(0, (end - now).days)
    elif sub.status == SubscriptionStatus.GRACE_PERIOD and sub.grace_period_ends_at:
        grace = sub.grace_period_ends_at.replace(tzinfo=timezone.utc)
        days_left = max(0, (grace - now).days)

    # plan_type и status могут быть str (из БД) или Enum; нормализуем
    def to_str(v):
        return v.value if hasattr(v, "value") else str(v)

    return SubscriptionResponse(
        id=sub.id,
        company_id=sub.company_id,
        plan_type=to_str(sub.plan_type),
        status=to_str(sub.status),
        start_date=sub.start_date,
        end_date=sub.end_date,
        grace_period_ends_at=sub.grace_period_ends_at,
        monthly_price=float(sub.monthly_price),
        currency=sub.currency,
        is_active=sub.is_active(),
        days_left=days_left,
    )


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_my_subscription(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    sub = await get_subscription(session, current_user.company_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подписка не найдена",
        )
    return _build_response(sub)


@router.post("/activate", response_model=SubscriptionResponse)
async def activate_my_subscription(
    body: ActivateSubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
):
    sub = await activate_subscription(session, current_user.company_id, body.months)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подписка не найдена",
        )
    return _build_response(sub)
