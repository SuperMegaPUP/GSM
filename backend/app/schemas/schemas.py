from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.models import FluidType, NodeType, UserRole


# =============================================================
# Аутентификация
# =============================================================

class LoginRequest(BaseModel):
    """Запрос на вход в систему."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT-токен после успешного входа."""
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    """Создание нового пользователя (только для admin)."""
    email: str
    password: str = Field(min_length=6)
    full_name: str
    role: UserRole = UserRole.manager


class UserResponse(BaseModel):
    """Ответ с данными пользователя."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    company_id: UUID
    created_at: datetime


# =============================================================
# Поиск и каталог
# =============================================================

class CarSearchRequest(BaseModel):
    """Запрос на подбор масла по параметрам автомобиля."""
    brand: str = Field(description="Марка авто, например Honda")
    model: str = Field(description="Модель, например Accord")
    year: int = Field(ge=1960, le=2030)
    engine_code: Optional[str] = Field(
        None, description="Код двигателя, например K20A"
    )
    engine_volume: Optional[float] = Field(
        None, description="Объём двигателя, л"
    )
    body_type: Optional[str] = Field(
        None, description="Тип кузова, например LA-CL7"
    )


class CarBrandResponse(BaseModel):
    """Марка автомобиля."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name_ru: str
    name_en: Optional[str] = None
    country: Optional[str] = None


class CarModelResponse(BaseModel):
    """Модель автомобиля."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    brand_id: UUID
    name: str
    generation: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None


class CarVariantResponse(BaseModel):
    """Конкретная модификация автомобиля."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    model_id: UUID
    engine_code: Optional[str] = None
    engine_volume: Optional[float] = None
    body_type: Optional[str] = None
    fuel_type: Optional[str] = None
    drive_type: Optional[str] = None
    transmission_type: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None


class FluidResponse(BaseModel):
    """Информация о жидкости/масле."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    canonical_name: str
    brand: Optional[str] = None
    product_line: Optional[str] = None
    viscosity_sae: Optional[str] = Field(
        None, description="Вязкость SAE, например 5W-30"
    )
    api_class: Optional[str] = Field(
        None, description="Класс API: SN, SP, CJ-4"
    )
    acea_class: Optional[str] = Field(
        None, description="Класс ACEA: A3/B4, C3"
    )
    oem_approvals: list = Field(
        default_factory=list,
        description="OEM-допуски: [\"VW 502.00\", \"MB 229.5\"]",
    )
    fluid_type: FluidType


class RecommendationResponse(BaseModel):
    """Рекомендация: узел + жидкость + объём + маркер OEM/Допуск."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    car_variant_id: UUID
    node_type: NodeType
    fluid: FluidResponse
    volume_liters: Optional[float] = Field(
        None, description="Объём жидкости в литрах"
    )
    volume_with_filter: Optional[float] = Field(
        None, description="Объём с учётом фильтра"
    )
    is_oem_recommendation: bool = Field(
        description="True = заводская рекомендация (🟢), False = допуск (🟡)"
    )
    oem_specification: Optional[str] = Field(
        None, description="Оригинальная спецификация, например Honda HMMF"
    )
    confidence_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Уверенность 0.0–1.0"
    )
