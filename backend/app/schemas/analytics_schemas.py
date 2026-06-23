from datetime import date
from uuid import UUID

from pydantic import BaseModel


class ActionItem(BaseModel):
    type: str
    severity: str
    message: str


class DailyActionPlanResponse(BaseModel):
    id: UUID
    company_id: UUID
    plan_date: date
    items: list[ActionItem]

    model_config = {"from_attributes": True}
