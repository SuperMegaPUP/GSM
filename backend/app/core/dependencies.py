import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session, set_tenant_id, text
from app.core.security import decode_access_token
from app.models.models import User

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
