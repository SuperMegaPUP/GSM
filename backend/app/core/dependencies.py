import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session, set_tenant_id, text
from app.core.security import decode_access_token
from app.models.models import User
from app.models.subscription import Subscription, SubscriptionStatus

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_active_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
        )

    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    company_id = payload.get("company_id")

    if not user_id or not company_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
        )

    parsed_company_id = uuid.UUID(company_id)

    set_tenant_id(parsed_company_id)
    await session.execute(
        text(
            f"SELECT set_config('app.current_tenant_id', "
            f"'{company_id}', true)"
        )
    )

    result = await session.execute(
        select(User).where(
            User.id == uuid.UUID(user_id), User.is_active == True
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или деактивирован",
        )

    return user


async def require_active_subscription(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    result = await session.execute(
        select(Subscription).where(
            Subscription.company_id == current_user.company_id
        )
    )
    sub = result.scalar_one_or_none()

    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "subscription_not_found",
                "message": "Подписка не найдена",
            },
        )

    if sub.status in (SubscriptionStatus.SUSPENDED, SubscriptionStatus.BLOCKED):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "subscription_expired",
                "status": sub.status.value,
                "message": "Подписка приостановлена. Оплатите для восстановления доступа",
            },
        )

    if sub.status == SubscriptionStatus.GRACE_PERIOD:
        now = datetime.now(timezone.utc)
        if sub.grace_period_ends_at:
            grace = sub.grace_period_ends_at.replace(tzinfo=timezone.utc)
            days_left = max(0, (grace - now).days)
        else:
            days_left = 0
        request.state.grace_days_left = days_left

    return current_user
