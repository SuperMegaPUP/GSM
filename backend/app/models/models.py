import enum
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


# =============================================================
# ENUMs (зеркалят SQL-типы из init.sql)
# =============================================================

class UserRole(str, enum.Enum):
    admin = "admin"
    supervisor = "supervisor"
    manager = "manager"
    technologist = "technologist"


class FluidType(str, enum.Enum):
    engine_oil = "engine_oil"
    manual_transmission = "manual_transmission"
    auto_transmission = "auto_transmission"
    cvt = "cvt"
    differential = "differential"
    transfer_case = "transfer_case"
    steering = "steering"
    brake = "brake"
    coolant = "coolant"


class NodeType(str, enum.Enum):
    ENGINE = "ENGINE"
    MANUAL_TRANSMISSION = "MANUAL_TRANSMISSION"
    AUTO_TRANSMISSION = "AUTO_TRANSMISSION"
    CVT = "CVT"
    TRANSFER_CASE = "TRANSFER_CASE"
    FRONT_DIFF = "FRONT_DIFF"
    REAR_DIFF = "REAR_DIFF"
    STEERING = "STEERING"
    BRAKE = "BRAKE"
    COOLANT = "COOLANT"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    grace_period = "grace_period"
    suspended = "suspended"
    blocked = "blocked"


class ImportStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    review = "review"
    completed = "completed"
    failed = "failed"


# =============================================================
# TenantAwareMixin — добавляет id (UUID) + company_id
# =============================================================

class TenantAwareMixin:
    """Для всех таблиц с изоляцией по tenant (company_id)."""

    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )


# =============================================================
# Модели
# =============================================================

class Company(Base, TimestampMixin):
    """Компания-клиент (тенант)."""

    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        default=SubscriptionStatus.active
    )
    grace_period_ends_at: Mapped[Optional[datetime]]
    settings: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    # Связи
    users: Mapped[list["User"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class User(Base, TimestampMixin, TenantAwareMixin):
    """Пользователь системы."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[UserRole] = mapped_column(default=UserRole.manager)
    is_active: Mapped[bool] = mapped_column(default=True)

    # Связи
    company: Mapped["Company"] = relationship(back_populates="users")


class CarBrand(Base, TimestampMixin, TenantAwareMixin):
    """Марка автомобиля."""

    __tablename__ = "car_brands"

    name_ru: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[Optional[str]] = mapped_column(String(100))

    # Связи
    models: Mapped[list["CarModel"]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )


class CarModel(Base, TimestampMixin, TenantAwareMixin):
    """Модель автомобиля."""

    __tablename__ = "car_models"

    brand_id: Mapped[UUID] = mapped_column(
        ForeignKey("car_brands.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    generation: Mapped[Optional[str]] = mapped_column(String(100))
    year_start: Mapped[Optional[int]]
    year_end: Mapped[Optional[int]]

    # Связи
    brand: Mapped["CarBrand"] = relationship(back_populates="models")
    variants: Mapped[list["CarVariant"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class CarVariant(Base, TimestampMixin, TenantAwareMixin):
    """Конкретная модификация автомобиля (двигатель, кузов, годы)."""

    __tablename__ = "car_variants"

    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("car_models.id", ondelete="CASCADE"), nullable=False
    )
    engine_code: Mapped[Optional[str]] = mapped_column(String(50))
    engine_volume: Mapped[Optional[float]]
    fuel_type: Mapped[Optional[str]] = mapped_column(String(20))
    body_type: Mapped[Optional[str]] = mapped_column(String(50))
    drive_type: Mapped[Optional[str]] = mapped_column(String(20))
    transmission_type: Mapped[Optional[str]] = mapped_column(String(20))
    year_start: Mapped[Optional[int]]
    year_end: Mapped[Optional[int]]
    source_hash: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True
    )

    # Связи
    model: Mapped["CarModel"] = relationship(back_populates="variants")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="car_variant", cascade="all, delete-orphan"
    )


class Fluid(Base, TimestampMixin, TenantAwareMixin):
    """Жидкость / масло с классификациями и допусками."""

    __tablename__ = "fluids"

    canonical_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    brand: Mapped[Optional[str]] = mapped_column(String(100))
    product_line: Mapped[Optional[str]] = mapped_column(String(100))
    viscosity_sae: Mapped[Optional[str]] = mapped_column(
        String(20), comment="Вязкость по SAE, например 5W-30"
    )
    api_class: Mapped[Optional[str]] = mapped_column(
        String(20), comment="Класс API: SN, SP, CJ-4 и т.д."
    )
    acea_class: Mapped[Optional[str]] = mapped_column(
        String(20), comment="Класс ACEA: A3/B4, C3 и т.д."
    )
    oem_approvals: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
        comment="Список OEM-допусков: [\"VW 502.00\", \"MB 229.5\"]",
    )
    fluid_type: Mapped[FluidType] = mapped_column(
        default=FluidType.engine_oil
    )
    hash_signature: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, comment="Хэш для дедупликации"
    )

    # Связи
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="fluid", cascade="all, delete-orphan"
    )


class Recommendation(Base, TimestampMixin, TenantAwareMixin):
    """Связка: вариант авто → узел → жидкость (с объёмом и маркером OEM/Допуск)."""

    __tablename__ = "recommendations"

    car_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("car_variants.id", ondelete="CASCADE"), nullable=False
    )
    node_type: Mapped[NodeType] = mapped_column(
        comment="Узел: ENGINE, AUTO_TRANSMISSION, DIFF и т.д."
    )
    fluid_id: Mapped[UUID] = mapped_column(
        ForeignKey("fluids.id", ondelete="CASCADE"), nullable=False
    )
    volume_liters: Mapped[Optional[float]] = mapped_column(
        comment="Объём жидкости в литрах"
    )
    volume_with_filter: Mapped[Optional[float]] = mapped_column(
        comment="Объём с учётом фильтра"
    )
    is_oem_recommendation: Mapped[bool] = mapped_column(
        default=False,
        comment="True = заводская рекомендация, False = допуск/аналог",
    )
    oem_specification: Mapped[Optional[str]] = mapped_column(
        String(100),
        comment="Оригинальная спецификация, например Honda HMMF",
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        comment="Уверенность в рекомендации: 0.0–1.0"
    )
    source: Mapped[Optional[str]] = mapped_column(
        String(100), comment="Источник данных (имя файла)"
    )

    # Связи
    car_variant: Mapped["CarVariant"] = relationship(back_populates="recommendations")
    fluid: Mapped["Fluid"] = relationship(back_populates="recommendations")


class ImportBatch(Base, TimestampMixin, TenantAwareMixin):
    """Журнал импортов Excel-файлов."""

    __tablename__ = "import_batches"

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[ImportStatus] = mapped_column(default=ImportStatus.pending)
    total_rows: Mapped[int] = mapped_column(default=0)
    new_rows: Mapped[int] = mapped_column(default=0)
    duplicates: Mapped[int] = mapped_column(default=0)
    errors: Mapped[int] = mapped_column(default=0)
    review_notes: Mapped[Optional[str]] = mapped_column(Text)


class StagingRow(Base, TimestampMixin, TenantAwareMixin):
    """Сырые данные из Excel до модерации технологом."""

    __tablename__ = "staging_rows"

    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False
    )
    raw_data: Mapped[dict] = mapped_column(
        JSONB, nullable=False, comment="Исходные данные из Excel"
    )
    parsed_data: Mapped[Optional[dict]] = mapped_column(
        JSONB, comment="Нормализованные данные после LLM-очистки"
    )
    validation_status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )
    duplicate_of: Mapped[Optional[UUID]] = mapped_column(
        comment="ID дублирующей записи (если найден дубль)"
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
