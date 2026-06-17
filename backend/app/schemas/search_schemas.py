from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CarSearchSchema(BaseModel):
    brand: str = Field(..., min_length=1, description="Марка автомобиля")
    model: str = Field(..., min_length=1, description="Модель автомобиля")
    year: Optional[int] = Field(None, ge=1960, le=2030, description="Год выпуска")
    engine_code: Optional[str] = Field(None, max_length=50, description="Код двигателя")
    engine_volume: Optional[float] = Field(None, gt=0, description="Объём двигателя, л")


class FluidSearchResult(BaseModel):
    fluid_id: UUID
    canonical_name: str
    brand: Optional[str] = None
    product_line: Optional[str] = None
    viscosity_sae: Optional[str] = None
    api_class: Optional[str] = None
    acea_class: Optional[str] = None
    oem_approvals: list = []
    fluid_type: str
    volume_liters: Optional[float] = None
    volume_with_filter: Optional[float] = None
    is_oem_recommendation: bool
    confidence_score: Optional[float] = None
    oem_specification: Optional[str] = None


class NodeGroupResult(BaseModel):
    node_type: str
    node_label: str
    recommendations: list[FluidSearchResult]


class SearchResponse(BaseModel):
    found_by: str
    variant_id: Optional[UUID] = None
    brand: str
    model: str
    engine_code: Optional[str] = None
    engine_volume: Optional[float] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    groups: list[NodeGroupResult]
