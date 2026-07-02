import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_active_user
from app.models.models import User
from app.schemas.sales_schemas import (
    CaseResponse,
    FeedbackRequest,
    ObjectionRequest,
    StatsResponse,
)
from app.services.sales_copilot import sales_copilot_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sales", tags=["Sales Copilot"])


@router.post("/handle-objection")
async def handle_objection(
    body: ObjectionRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    """Sales Copilot 2.0 — structured SSE stream.

    Events:
      - rag_cases     — найденные кейсы (показываются ПЕРВЫМИ)
      - variant_start — начало варианта (rational|empathetic|take_charge)
      - variant_chunk — чанк текста
      - variant_done  — вариант завершён
      - done          — всё готово
      - error         — ошибка
    """
    async def event_stream():
        try:
            async for chunk in sales_copilot_stream(
                objection=body.objection,
                tenant_id=current_user.company_id,
                db=session,
                category=body.category,
                car_brand=body.car_brand,
                fluid_type=body.fluid_type,
                context_chips=body.context_chips,
            ):
                yield chunk
        except Exception as e:
            logger.exception("handle_objection failed")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/objection-cases/{case_id}/feedback")
async def log_feedback(
    case_id: str,
    body: FeedbackRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    result = await session.execute(
        text("SELECT * FROM record_objection_feedback(:cid, :tid, CAST(:outcome AS objection_outcome), :comment)"),
        {
            "cid": case_id,
            "tid": current_user.company_id,
            "outcome": body.outcome,
            "comment": body.comment or "",
        },
    )
    row = result.fetchone()
    await session.commit()
    return {
        "status": "ok",
        "success_rate": float(row[0]) if row else None,
        "needs_review": bool(row[1]) if row else None,
    }


@router.get("/objection-cases")
async def list_cases(
    category: Optional[str] = Query(None),
    needs_review: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    offset = (page - 1) * per_page
    rows = await session.execute(
        text("""
            SELECT id, number, category, category_label,
                   objection_text, response_text, tags,
                   outcome, usage_count, success_count, failure_count,
                   last_used_at, is_seed, source, needs_review,
                   car_brand, fluid_type,
                   objection_case_success_rate(objection_cases) AS success_rate
            FROM objection_cases
            WHERE (is_seed = true OR tenant_id = :tenant_id)
              AND is_published = true
              AND (:category IS NULL OR category = :category::objection_category)
              AND (:needs_review IS NULL OR needs_review = :needs_review)
            ORDER BY is_seed DESC, success_rate DESC NULLS LAST, usage_count DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "tenant_id": current_user.company_id,
            "category": category,
            "needs_review": needs_review,
            "limit": per_page,
            "offset": offset,
        },
    )
    return [
        CaseResponse(
            id=r.id,
            number=r.number,
            category=r.category,
            category_label=r.category_label,
            objection_text=r.objection_text,
            response_text=r.response_text,
            tags=r.tags or [],
            usage_count=r.usage_count or 0,
            success_count=r.success_count or 0,
            failure_count=r.failure_count or 0,
            success_rate=float(r.success_rate) if r.success_rate else 0.5,
            is_seed=r.is_seed,
            source=r.source,
            car_brand=r.car_brand,
            fluid_type=r.fluid_type,
        )
        for r in rows
    ]


@router.get("/objection-cases/stats", response_model=StatsResponse)
async def case_stats(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    rows = await session.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE is_seed = true) AS seed_count,
                COALESCE(SUM(usage_count), 0) AS total_used,
                COALESCE(SUM(success_count), 0) AS total_won,
                COALESCE(SUM(failure_count), 0) AS total_lost,
                AVG(objection_case_success_rate(objection_cases))
                    FILTER (WHERE usage_count > 0) AS avg_success_rate,
                COUNT(*) FILTER (WHERE needs_review = true) AS needs_review_count
            FROM objection_cases
            WHERE is_seed = true OR tenant_id = :tenant_id
        """),
        {"tenant_id": current_user.company_id},
    )
    row = rows.fetchone()
    return StatsResponse(
        total=row.total or 0,
        seed_count=row.seed_count or 0,
        total_used=row.total_used or 0,
        total_won=row.total_won or 0,
        total_lost=row.total_lost or 0,
        avg_success_rate=float(row.avg_success_rate) if row.avg_success_rate else None,
        needs_review_count=row.needs_review_count or 0,
    )


@router.get("/objection-cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    row = await session.execute(
        text("""
            SELECT id, number, category, category_label,
                   objection_text, response_text, tags,
                   outcome, usage_count, success_count, failure_count,
                   last_used_at, is_seed, source, needs_review,
                   car_brand, fluid_type,
                   objection_case_success_rate(objection_cases) AS success_rate
            FROM objection_cases
            WHERE id = :case_id
              AND (is_seed = true OR tenant_id = :tenant_id)
              AND is_published = true
        """),
        {
            "case_id": case_id,
            "tenant_id": current_user.company_id,
        },
    )
    r = row.fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail="Кейс не найден")
    return CaseResponse(
        id=r.id,
        number=r.number,
        category=r.category,
        category_label=r.category_label,
        objection_text=r.objection_text,
        response_text=r.response_text,
        tags=r.tags or [],
        usage_count=r.usage_count or 0,
        success_count=r.success_count or 0,
        failure_count=r.failure_count or 0,
        success_rate=float(r.success_rate) if r.success_rate else 0.5,
        is_seed=r.is_seed,
        source=r.source,
        car_brand=r.car_brand,
        fluid_type=r.fluid_type,
    )
