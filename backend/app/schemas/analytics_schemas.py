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


class TrendPoint(BaseModel):
    date: str
    value: dict


class TrendsResponse(BaseModel):
    objections_total: list[TrendPoint]
    objections_by_category: list[TrendPoint]
    case_stats: list[TrendPoint]


class InsightItem(BaseModel):
    type: str
    severity: str
    message: str


class InsightsResponse(BaseModel):
    insights: list[InsightItem]


class CaseHistoryItem(BaseModel):
    interaction_id: int
    objection: str
    category: str | None
    created_at: str
    outcome: str | None


class CaseHistoryResponse(BaseModel):
    case_id: str
    usage_count: int
    success_count: int
    failure_count: int
    success_rate: float
    history: list[CaseHistoryItem]
