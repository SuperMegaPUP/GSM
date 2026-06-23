import enum
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class PlanType(str, enum.Enum):
    BASIC = "BASIC"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    GRACE_PERIOD = "GRACE_PERIOD"
    SUSPENDED = "SUSPENDED"
    BLOCKED = "BLOCKED"


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    plan_type: Mapped[PlanType] = mapped_column(
        String(20),
        default=PlanType.BASIC,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(20),
        default=SubscriptionStatus.ACTIVE,
    )
    start_date: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"),
    )
    end_date: Mapped[datetime] = mapped_column(nullable=False)
    grace_period_ends_at: Mapped[Optional[datetime]]
    monthly_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")

    company: Mapped["Company"] = relationship(back_populates="subscription")

    def is_active(self) -> bool:
        s = self.status.value if hasattr(self.status, "value") else str(self.status)
        return s in ("ACTIVE", "GRACE_PERIOD")
