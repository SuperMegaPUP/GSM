from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_active_user
from app.models.models import User, UserRole
from app.schemas.catalog_schemas import (
    PaginatedResponse,
    CarBrandCreate,
    CarBrandRead,
    CarBrandUpdate,
    CarModelCreate,
    CarModelRead,
    CarVariantCreate,
    CarVariantRead,
    FluidCreate,
    FluidRead,
)
from app.services.crud import (
    DuplicateError,
    NotFoundError,
    list_brands,
    create_brand,
    get_brand,
    update_brand,
    list_models,
    create_model,
    list_variants,
    create_variant,
    list_fluids,
    create_fluid,
    get_fluid,
)

router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


# =============================================================
# Вспомогательная зависимость — проверка роли
# =============================================================

def require_role(allowed_roles: set[UserRole]):
    async def _check_role(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав",
            )
        return current_user
    return _check_role


require_supervisor = require_role({UserRole.admin, UserRole.supervisor})


# =============================================================
# CarBrand
# =============================================================

@router.get("/brands", response_model=PaginatedResponse[CarBrandRead])
async def get_brands(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(None, min_length=1),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    items, total = await list_brands(
        session, current_user.company_id, limit=limit, offset=offset, search=search
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/brands", response_model=CarBrandRead, status_code=201)
async def post_brand(
    body: CarBrandCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_supervisor),
):
    try:
        brand = await create_brand(session, current_user.company_id, body)
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return brand


@router.get("/brands/{brand_id}", response_model=CarBrandRead)
async def get_brand_by_id(
    brand_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    brand = await get_brand(session, current_user.company_id, brand_id)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Марка не найдена")
    return brand


@router.patch("/brands/{brand_id}", response_model=CarBrandRead)
async def patch_brand(
    brand_id: UUID,
    body: CarBrandUpdate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_supervisor),
):
    try:
        brand = await update_brand(session, current_user.company_id, brand_id, body)
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return brand


# =============================================================
# CarModel
# =============================================================

@router.get("/models", response_model=PaginatedResponse[CarModelRead])
async def get_models(
    brand_id: Optional[UUID] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(None, min_length=1),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    items, total = await list_models(
        session, current_user.company_id,
        brand_id=brand_id, limit=limit, offset=offset, search=search,
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/models", response_model=CarModelRead, status_code=201)
async def post_model(
    body: CarModelCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_supervisor),
):
    try:
        model = await create_model(session, current_user.company_id, body)
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return model


# =============================================================
# CarVariant
# =============================================================

@router.get("/variants", response_model=PaginatedResponse[CarVariantRead])
async def get_variants(
    model_id: Optional[UUID] = Query(None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    items, total = await list_variants(
        session, current_user.company_id,
        model_id=model_id, limit=limit, offset=offset,
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/variants", response_model=CarVariantRead, status_code=201)
async def post_variant(
    body: CarVariantCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    variant = await create_variant(session, current_user.company_id, body)
    return variant


# =============================================================
# Fluid
# =============================================================

@router.get("/fluids", response_model=PaginatedResponse[FluidRead])
async def get_fluids(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: Optional[str] = Query(None, min_length=1),
    fluid_type: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    items, total = await list_fluids(
        session, current_user.company_id,
        limit=limit, offset=offset, search=search, fluid_type=fluid_type,
    )
    return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/fluids", response_model=FluidRead, status_code=201)
async def post_fluid(
    body: FluidCreate,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    try:
        fluid = await create_fluid(session, current_user.company_id, body)
    except DuplicateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return fluid


@router.get("/fluids/{fluid_id}", response_model=FluidRead)
async def get_fluid_by_id(
    fluid_id: UUID,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    fluid = await get_fluid(session, current_user.company_id, fluid_id)
    if fluid is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Жидкость не найдена"
        )
    return fluid
