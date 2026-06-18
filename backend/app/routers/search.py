from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_active_user
from app.models.models import User
from app.schemas.oil_expert import OilExpertResponse
from app.schemas.search_schemas import CarSearchSchema, SearchResponse
from app.services.oil_expert import explain_recommendation_cached
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


@router.get("/explain/{fluid_id}", response_model=OilExpertResponse)
async def explain_oil(
    request: Request,
    fluid_id: UUID,
    car_variant_id: UUID = Query(..., description="ID варианта автомобиля"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """AI-эксперт: краткое пояснение, почему масло подходит для автомобиля."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis не инициализирован",
        )

    explanation, cached = await explain_recommendation_cached(
        fluid_id=fluid_id,
        car_variant_id=car_variant_id,
        db=session,
        redis=redis,
    )

    return OilExpertResponse(
        fluid_id=fluid_id,
        car_variant_id=car_variant_id,
        explanation=explanation,
        cached=cached,
    )
