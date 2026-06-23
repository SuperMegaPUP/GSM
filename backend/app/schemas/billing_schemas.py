from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    id: UUID
    company_id: UUID
    plan_type: str
    status: str
    start_date: datetime
    end_date: datetime
    grace_period_ends_at: Optional[datetime] = None
    monthly_price: float
    currency: str
    is_active: bool
    days_left: Optional[int] = None

    model_config = {"from_attributes": True}


class ActivateSubscriptionRequest(BaseModel):
    months: int = 1
