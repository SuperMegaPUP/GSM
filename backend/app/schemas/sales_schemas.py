from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ObjectionRequest(BaseModel):
    objection: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = Field(None, description="Контекст: что предлагаем, ситуация")
    category: Optional[str] = None
    car_brand: Optional[str] = None
    fluid_type: Optional[str] = None
    context_chips: Optional[list] = None


class ObjectionVariant(BaseModel):
    style: str = Field(..., description="Стиль ответа: rational / empathetic / take_charge")
    label: str = Field(..., description="Название варианта")
    text: str = Field(..., description="Текст ответа")


class ObjectionResponse(BaseModel):
    variants: list[ObjectionVariant]


class FeedbackRequest(BaseModel):
    outcome: str = Field(..., description="closed_won или closed_lost")
    comment: Optional[str] = None


class CaseResponse(BaseModel):
    id: str
    number: Optional[int]
    category: str
    category_label: str
    objection_text: str
    response_text: str
    tags: list[str]
    usage_count: int
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.5
    is_seed: bool = False
    source: str = "seed"
    car_brand: Optional[str] = None
    fluid_type: Optional[str] = None


class StatsResponse(BaseModel):
    total: int
    seed_count: int
    total_used: int
    total_won: int
    total_lost: int
    avg_success_rate: Optional[float]
    needs_review_count: int
