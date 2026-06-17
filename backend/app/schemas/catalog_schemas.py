from datetime import datetime
from typing import Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import FluidType

T = TypeVar("T")


# =============================================================
# Обёртка для пагинированного ответа
# =============================================================

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


# =============================================================
# CarBrand
# =============================================================

class CarBrandCreate(BaseModel):
    name_ru: str = Field(min_length=1, max_length=100)
    name_en: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)


class CarBrandUpdate(BaseModel):
    name_ru: Optional[str] = Field(None, min_length=1, max_length=100)
    name_en: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)


class CarBrandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name_ru: str
    name_en: Optional[str] = None
    country: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# =============================================================
# CarModel
# =============================================================

class CarModelCreate(BaseModel):
    brand_id: UUID
    name: str = Field(min_length=1, max_length=100)
    generation: Optional[str] = Field(None, max_length=100)
    year_start: Optional[int] = Field(None, ge=1960, le=2030)
    year_end: Optional[int] = Field(None, ge=1960, le=2030)


class CarModelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand_id: UUID
    name: str
    generation: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# =============================================================
# CarVariant
# =============================================================

class CarVariantCreate(BaseModel):
    model_id: UUID
    engine_code: Optional[str] = Field(None, max_length=50)
    engine_volume: Optional[float] = Field(None, gt=0)
    fuel_type: Optional[str] = Field(None, max_length=20)
    body_type: Optional[str] = Field(None, max_length=50)
    drive_type: Optional[str] = Field(None, max_length=20)
    transmission_type: Optional[str] = Field(None, max_length=20)
    year_start: Optional[int] = Field(None, ge=1960, le=2030)
    year_end: Optional[int] = Field(None, ge=1960, le=2030)


class CarVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_id: UUID
    engine_code: Optional[str] = None
    engine_volume: Optional[float] = None
    fuel_type: Optional[str] = None
    body_type: Optional[str] = None
    drive_type: Optional[str] = None
    transmission_type: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    created_at: datetime
    updated_at: datetime


# =============================================================
# Fluid
# =============================================================

class FluidCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=255)
    brand: Optional[str] = Field(None, max_length=100)
    product_line: Optional[str] = Field(None, max_length=100)
    viscosity_sae: Optional[str] = Field(None, max_length=20)
    api_class: Optional[str] = Field(None, max_length=20)
    acea_class: Optional[str] = Field(None, max_length=20)
    oem_approvals: list[str] = Field(default_factory=list)
    fluid_type: FluidType = FluidType.engine_oil


class FluidUpdate(BaseModel):
    canonical_name: Optional[str] = Field(None, min_length=1, max_length=255)
    brand: Optional[str] = Field(None, max_length=100)
    product_line: Optional[str] = Field(None, max_length=100)
    viscosity_sae: Optional[str] = Field(None, max_length=20)
    api_class: Optional[str] = Field(None, max_length=20)
    acea_class: Optional[str] = Field(None, max_length=20)
    oem_approvals: Optional[list[str]] = None
    fluid_type: Optional[FluidType] = None


class FluidRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_name: str
    brand: Optional[str] = None
    product_line: Optional[str] = None
    viscosity_sae: Optional[str] = None
    api_class: Optional[str] = None
    acea_class: Optional[str] = None
    oem_approvals: list
    fluid_type: FluidType
    created_at: datetime
    updated_at: datetime
