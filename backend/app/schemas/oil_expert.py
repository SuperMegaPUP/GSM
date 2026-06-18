from uuid import UUID

from pydantic import BaseModel, Field


class OilExpertResponse(BaseModel):
    fluid_id: UUID = Field(..., description="ID жидкости")
    car_variant_id: UUID = Field(..., description="ID варианта авто")
    explanation: str = Field(..., description="Экспертное пояснение")
    cached: bool = Field(False, description="Взят ли ответ из кэша Redis")
