from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CarSearchSchema(BaseModel):
    brand: Optional[str] = Field(None, min_length=1, description="Марка автомобиля")
    model: Optional[str] = Field(None, min_length=1, description="Модель автомобиля")
    year: Optional[int] = Field(None, ge=1960, le=2030, description="Год выпуска")
    engine_code: Optional[str] = Field(None, max_length=50, description="Код двигателя")
    engine_volume: Optional[float] = Field(None, gt=0, description="Объём двигателя, л")

    @model_validator(mode='after')
    def validate_at_least_one_field(self) -> "CarSearchSchema":
        if not any([self.brand, self.model, self.year, self.engine_code]):
            raise ValueError("Необходимо указать хотя бы один параметр поиска (марка, модель, год или код двигателя)")
        return self


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


class ModelSearchInfo(BaseModel):
    """Информация о найденной модели автомобиля."""
    name: str
    engine_code: Optional[str] = None
    engine_volume: Optional[float] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    variants_count: int = 0


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
    models: list[ModelSearchInfo] = []
