import uuid
from datetime import date
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class DailyActionPlan(Base, TimestampMixin):
    __tablename__ = "daily_action_plans"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_date: Mapped[date] = mapped_column(nullable=False)
    items: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )


class DailyTrend(Base, TimestampMixin):
    __tablename__ = "daily_trends"
    __table_args__ = (
        UniqueConstraint("company_id", "date", "metric"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    trend_date: Mapped[date] = mapped_column("date", nullable=False)
    metric: Mapped[str] = mapped_column(nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
