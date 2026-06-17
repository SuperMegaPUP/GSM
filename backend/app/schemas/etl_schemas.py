from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.models import FluidType, ImportStatus


class RawExcelRow(BaseModel):
    """Сырая строка из Excel-файла до обработки и нормализации."""

    brand: Optional[str] = Field(None, description="Марка авто")
    model: Optional[str] = Field(None, description="Модель авто")
    years: Optional[str] = Field(
        None, description="Годы выпуска, например 93.09-97.08"
    )
    body: Optional[str] = Field(None, description="Кузов, например LA-CL7")
    engine: Optional[str] = Field(
        None, description="Код двигателя, например K20A"
    )
    engine_volume: Optional[str] = Field(
        None, description="Объём двигателя, например 2.0"
    )
    node_type: Optional[str] = Field(
        None, description="Узел: ENGINE / ATF / DIFF и т.д."
    )
    fluid_name: Optional[str] = Field(
        None, description="Сырое название масла из файла"
    )
    volume: Optional[str] = Field(None, description="Объём в литрах")
    volume_with_filter: Optional[str] = Field(
        None, description="Объём с фильтром"
    )
    viscosity: Optional[str] = Field(
        None, description="Вязкость SAE, например 10W-30"
    )
    api_class: Optional[str] = Field(
        None, description="Класс API, например SJ/GF-2"
    )
    oem_spec: Optional[str] = Field(
        None, description="OEM-спецификация, например ATF TYPE T-IV"
    )


class NormalizedFluid(BaseModel):
    """Нормализованные данные о жидкости после LLM-очистки."""

    canonical_name: str = Field(
        description="Каноническое имя (нормализованное)"
    )
    brand: Optional[str] = Field(None, description="Бренд производителя")
    product_line: Optional[str] = Field(
        None, description="Линейка продукта"
    )
    viscosity_sae: Optional[str] = Field(
        None, description="Вязкость SAE, например 5W-30"
    )
    api_class: Optional[str] = Field(None, description="Класс API")
    acea_class: Optional[str] = Field(None, description="Класс ACEA")
    oem_approvals: list[str] = Field(
        default_factory=list, description="Список OEM-допусков"
    )
    fluid_type: FluidType = Field(
        default=FluidType.engine_oil, description="Тип жидкости"
    )


class ImportBatchResponse(BaseModel):
    """Ответ с информацией о batch-импорте."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    status: ImportStatus
    total_rows: int
    new_rows: int
    duplicates: int
    errors: int
    uploaded_by: Optional[UUID] = None
    created_at: datetime
