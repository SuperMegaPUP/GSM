import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import SubscriptionStatus as OldStatus
from app.models.subscription import Subscription, SubscriptionStatus, PlanType

logger = logging.getLogger(__name__)


async def check_and_update_subscriptions(db: AsyncSession) -> int:
    """Переводит ACTIVE → GRACE_PERIOD, если end_date истёк."""
    now = datetime.utcnow()
    stmt = (
        select(Subscription)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .where(Subscription.end_date < now)
    )
    result = await db.execute(stmt)
    expired = result.scalars().all()

    for sub in expired:
        sub.status = SubscriptionStatus.GRACE_PERIOD
        sub.grace_period_ends_at = now + timedelta(days=3)
        logger.info(
            "Абонемент %s переведён в GRACE_PERIOD (истёк %s)",
            sub.company_id, sub.end_date,
        )

    await db.commit()
    return len(expired)


async def suspend_expired(db: AsyncSession) -> int:
    """Переводит GRACE_PERIOD → SUSPENDED, если grace_period истёк."""
    now = datetime.utcnow()
    stmt = (
        select(Subscription)
        .where(Subscription.status == SubscriptionStatus.GRACE_PERIOD)
        .where(Subscription.grace_period_ends_at < now)
    )
    result = await db.execute(stmt)
    expired = result.scalars().all()

    for sub in expired:
        sub.status = SubscriptionStatus.SUSPENDED
        logger.info(
            "Абонемент %s переведён в SUSPENDED", sub.company_id,
        )

    await db.commit()
    return len(expired)


async def activate_subscription(
    db: AsyncSession,
    company_id: UUID,
    months: int = 1,
) -> Optional[Subscription]:
    """Продлевает подписку: устанавливает ACTIVE и сдвигает end_date."""
    result = await db.execute(
        select(Subscription).where(Subscription.company_id == company_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return None

    now = datetime.utcnow()
    new_end = max(sub.end_date, now) + timedelta(days=30 * months)
    sub.end_date = new_end
    sub.status = SubscriptionStatus.ACTIVE
    sub.grace_period_ends_at = None

    await db.commit()
    await db.refresh(sub)
    return sub


async def get_subscription(
    db: AsyncSession,
    company_id: UUID,
) -> Optional[Subscription]:
    result = await db.execute(
        select(Subscription).where(Subscription.company_id == company_id)
    )
    return result.scalar_one_or_none()
