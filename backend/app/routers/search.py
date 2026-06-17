from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_active_user
from app.models.models import User
from app.schemas.search_schemas import CarSearchSchema, SearchResponse
from app.services.search_engine import (
    find_recommendations,
    NotFoundError,
)

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("/oils", response_model=SearchResponse)
async def search_oils(
    request: Request,
    body: CarSearchSchema,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    qdrant = getattr(request.app.state, "qdrant", None)
    if qdrant is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qdrant не инициализирован",
        )

    try:
        result = await find_recommendations(
            params=body,
            tenant_id=current_user.company_id,
            db=session,
            qdrant=qdrant,
        )
    except NotFoundError:
        # Возвращаем пустой результат вместо 404 — фронтенд показывает empty state
        return SearchResponse(
            found_by="none",
            brand=body.brand or "",
            model=body.model or "",
            groups=[],
        )

    return result
