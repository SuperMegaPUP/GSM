import csv
import io
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.dependencies import get_current_active_user
from app.models.models import User
from app.schemas.sales_schemas import (
    KnowledgeUploadResponse,
    ObjectionRequest,
)
from app.services.sales_copilot import stream_objection_response
from app.services.sales_indexer import index_sales_objections

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sales", tags=["sales"])


@router.post("/handle-objection")
async def handle_objection(
    request: Request,
    body: ObjectionRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    qdrant = getattr(request.app.state, "qdrant", None)
    if qdrant is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qdrant не инициализирован",
        )

    return StreamingResponse(
        stream_objection_response(body, current_user.company_id, qdrant),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/upload-knowledge", response_model=KnowledgeUploadResponse)
async def upload_knowledge(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    qdrant = getattr(request.app.state, "qdrant", None)
    if qdrant is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Qdrant не инициализирован",
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл не указан",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пустой файл",
        )

    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        entries = _parse_csv(content)
    elif ext == "json":
        entries = _parse_json(content)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поддерживаются только CSV и JSON",
        )

    if not entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет записей для импорта",
        )

    count = await index_sales_objections(
        tenant_id=current_user.company_id,
        objections_data=entries,
        qdrant_client=qdrant,
    )

    return KnowledgeUploadResponse(
        imported=count,
        collection=f"sales_objections_{current_user.company_id}",
    )


# =============================================================
# Парсеры файлов
# =============================================================


def _parse_csv(content: bytes) -> list[dict]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    entries: list[dict] = []
    for row in reader:
        entry = {
            "category": row.get("category", "").strip(),
            "objection": row.get("objection", "").strip(),
            "core_argument": row.get("core_argument", "").strip(),
            "successful_reply": row.get("successful_reply", "").strip(),
        }
        if entry["objection"] and entry["core_argument"]:
            entries.append(entry)
    return entries


def _parse_json(content: bytes) -> list[dict]:
    data = json.loads(content.decode("utf-8"))
    if isinstance(data, dict):
        data = data.get("entries", data.get("knowledge", []))
    entries: list[dict] = []
    for item in data:
        entry = {
            "category": str(item.get("category", "")).strip(),
            "objection": str(item.get("objection", "")).strip(),
            "core_argument": str(item.get("core_argument", "")).strip(),
            "successful_reply": str(item.get("successful_reply", "")).strip(),
        }
        if entry["objection"] and entry["core_argument"]:
            entries.append(entry)
    return entries
