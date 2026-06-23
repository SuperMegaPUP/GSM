"""
GSM Sales Copilot — FastAPI Service Layer
==========================================

Implements the backend endpoints consumed by the MCP adapter.
Architecture:
  MCP adapter → HTTP → FastAPI → Qdrant (vector search) + PostgreSQL (FTS + metadata)

Endpoints:
  GET  /api/v1/sales/search-objection-cases
  GET  /api/v1/sales/objection-cases/{id}
  GET  /api/v1/sales/objection-categories
  POST /api/v1/sales/objection-cases/{id}/feedback
  POST /api/v1/sales/objection-cases          (create new — for technologist)
  POST /api/v1/sales/objection-cases/import   (bulk import from Excel/JSON)
  POST /api/v1/sales/handle-objection         (main: LLM + RAG pipeline)

Vector embeddings:
  Model: paraphrase-multilingual-MiniLM-L12-v2 (384 dims, multilingual, 90MB)
  Cached in Redis by content_hash for 7 days
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.core.config import settings
from app.services.qdrant_client import get_qdrant
from app.services.embedding import embed_text, embed_batch
from app.services.llm_client import llm_complete_stream
from app.models.models import User, ObjectionCase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sales", tags=["sales-copilot"])

# Qdrant collection name
COLLECTION = "sales_objections"
VECTOR_SIZE = 384  # paraphrase-multilingual-MiniLM-L12-v2


# ============================================================================
# Pydantic schemas
# ============================================================================

class SearchParams(BaseModel):
    q: str = Field(..., min_length=3, max_length=2000)
    category: Optional[str] = None
    car_brand: Optional[str] = None
    fluid_type: Optional[str] = None
    limit: int = Field(5, ge=1, le=10)
    min_score: float = Field(0.6, ge=0.0, le=1.0)


class CaseResponse(BaseModel):
    id: str
    number: Optional[int]
    category: str
    category_label: str
    objection_text: str
    response_text: str
    tags: list[str]
    usage_count: int
    quality_score: float
    score: Optional[float] = None


class SearchResponse(BaseModel):
    cases: list[CaseResponse]
    total: int
    search_method: str  # vector | fts | fallback


class FeedbackRequest(BaseModel):
    positive: bool
    comment: Optional[str] = None


class CreateCaseRequest(BaseModel):
    category: str
    category_label: str
    objection_text: str
    response_text: str
    tags: list[str] = []
    car_brand: Optional[str] = None
    fluid_type: Optional[str] = None
    is_seed: bool = False  # only technologist can set this


class HandleObjectionRequest(BaseModel):
    """Main endpoint: client objection → 3 AI-generated responses with RAG context."""
    objection: str = Field(..., min_length=3, max_length=2000)
    category: Optional[str] = None
    car_brand: Optional[str] = None
    fluid_type: Optional[str] = None
    context: Optional[str] = None  # previous dialog messages
    client_info: Optional[dict] = None  # name, company, etc.


# ============================================================================
# 1. Search objection cases (MCP-consumable)
# ============================================================================

@router.get("/search-objection-cases", response_model=SearchResponse)
async def search_objection_cases(
    request: Request,
    q: str = Query(..., min_length=3, max_length=2000),
    category: Optional[str] = Query(None),
    car_brand: Optional[str] = Query(None),
    fluid_type: Optional[str] = Query(None),
    limit: int = Query(5, ge=1, le=10),
    min_score: float = Query(0.6, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Semantic search for objection cases.

    Order of operations:
      1. Embed query (cached)
      2. Vector search in Qdrant with payload filters
      3. If Qdrant down or empty → fallback to PostgreSQL FTS
      4. Fetch full metadata from PostgreSQL by IDs
      5. Increment usage_count for returned cases
    """
    tenant_id = user.company_id

    # Build Qdrant filter
    must_conditions = [
        # Multi-tenant isolation: seed cases (global) OR own cases
        {"should": [
            {"key": "is_seed", "match": {"value": True}},
            {"key": "tenant_id", "match": {"value": str(tenant_id)}},
        ]},
        {"key": "is_published", "match": {"value": True}},
    ]
    if category:
        must_conditions.append({"key": "category", "match": {"value": category}})
    if car_brand:
        must_conditions.append({"key": "car_brand", "match": {"value": car_brand}})
    if fluid_type:
        must_conditions.append({"key": "fluid_type", "match": {"value": fluid_type}})

    try:
        # Embed query
        query_vector = await embed_text(q)

        # Qdrant search
        qdrant = await get_qdrant()
        hits = await qdrant.search(
            collection_name=COLLECTION,
            query_vector=query_vector,
            limit=limit * 2,  # over-fetch to filter by score
            query_filter={"must": must_conditions},
            with_payload=True,
        )

        # Filter by min_score
        cases_raw = [
            h for h in hits if h.score >= min_score
        ][:limit]

        if not cases_raw:
            # Fallback to FTS
            return await _fts_fallback(
                db, q, category, tenant_id, limit
            )

        # Fetch full case data from PostgreSQL by IDs
        case_ids = [h.payload.get("case_id") for h in cases_raw if h.payload.get("case_id")]
        if not case_ids:
            return await _fts_fallback(db, q, category, tenant_id, limit)

        # Batch fetch from PostgreSQL
        rows = await db.execute(
            text("""
                SELECT id, number, category, category_label,
                       objection_text, response_text, tags,
                       usage_count, quality_score
                FROM objection_cases
                WHERE id = ANY(:ids)
                  AND is_published = true
                  AND (is_seed = true OR tenant_id = :tenant_id)
                ORDER BY array_position(:ids, id)
            """),
            {"ids": case_ids, "tenant_id": tenant_id}
        )
        db_cases = {r.id: r for r in rows}

        # Merge Qdrant score + DB data
        cases = []
        for hit in cases_raw:
            cid = hit.payload.get("case_id")
            if cid in db_cases:
                r = db_cases[cid]
                cases.append(CaseResponse(
                    id=r.id,
                    number=r.number,
                    category=r.category,
                    category_label=r.category_label,
                    objection_text=r.objection_text,
                    response_text=r.response_text,
                    tags=r.tags or [],
                    usage_count=r.usage_count,
                    quality_score=r.quality_score,
                    score=hit.score,
                ))

        # Increment usage_count asynchronously
        if cases:
            await db.execute(
                text("SELECT increment_objection_case_usage(:id, :tenant_id)"),
                [{"id": c.id, "tenant_id": tenant_id} for c in cases]
            )
            await db.commit()

        return SearchResponse(
            cases=cases,
            total=len(cases),
            search_method="vector",
        )

    except Exception as e:
        logger.warning(f"Qdrant search failed, falling back to FTS: {e}")
        return await _fts_fallback(db, q, category, tenant_id, limit)


async def _fts_fallback(
    db: AsyncSession,
    q: str,
    category: Optional[str],
    tenant_id: uuid.UUID,
    limit: int,
) -> SearchResponse:
    """PostgreSQL full-text search fallback when Qdrant is unavailable."""
    sql = text("""
        SELECT id, number, category, category_label,
               objection_text, response_text, tags,
               usage_count, quality_score,
               ts_rank(
                   to_tsvector('russian', objection_text || ' ' || response_text),
                   plainto_tsquery('russian', :q)
               ) AS score
        FROM objection_cases
        WHERE is_published = true
          AND (is_seed = true OR tenant_id = :tenant_id)
          AND to_tsvector('russian', objection_text || ' ' || response_text)
              @@ plainto_tsquery('russian', :q)
          AND (:category IS NULL OR category = :category::objection_category)
        ORDER BY score DESC
        LIMIT :limit
    """)
    rows = await db.execute(sql, {
        "q": q, "tenant_id": tenant_id,
        "category": category, "limit": limit,
    })
    cases = [
        CaseResponse(
            id=r.id, number=r.number, category=r.category,
            category_label=r.category_label,
            objection_text=r.objection_text, response_text=r.response_text,
            tags=r.tags or [], usage_count=r.usage_count,
            quality_score=r.quality_score,
            score=float(r.score) if r.score else 0.0,
        )
        for r in rows
    ]
    return SearchResponse(cases=cases, total=len(cases), search_method="fts")


# ============================================================================
# 2. Get case by ID
# ============================================================================

@router.get("/objection-cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = await db.execute(
        text("""
            SELECT id, number, category, category_label,
                   objection_text, response_text, tags,
                   usage_count, quality_score
            FROM objection_cases
            WHERE id = :id
              AND is_published = true
              AND (is_seed = true OR tenant_id = :tenant_id)
        """),
        {"id": case_id, "tenant_id": user.company_id}
    )
    r = row.first()
    if not r:
        raise HTTPException(404, f"Case {case_id} not found")
    return CaseResponse(
        id=r.id, number=r.number, category=r.category,
        category_label=r.category_label,
        objection_text=r.objection_text, response_text=r.response_text,
        tags=r.tags or [], usage_count=r.usage_count,
        quality_score=r.quality_score,
    )


# ============================================================================
# 3. List categories with counts
# ============================================================================

@router.get("/objection-categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = await db.execute(
        text("""
            SELECT category, category_label, COUNT(*) AS count
            FROM objection_cases
            WHERE is_published = true
              AND (is_seed = true OR tenant_id = :tenant_id)
            GROUP BY category, category_label
            ORDER BY count DESC
        """),
        {"tenant_id": user.company_id}
    )
    return [
        {"category": r.category, "category_label": r.category_label, "count": r.count}
        for r in rows
    ]


# ============================================================================
# 4. Feedback (RLHF)
# ============================================================================

@router.post("/objection-cases/{case_id}/feedback")
async def post_feedback(
    case_id: str,
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    delta = 0.05 if body.positive else -0.1
    await db.execute(
        text("""
            UPDATE objection_cases
            SET quality_score = LEAST(1.0, GREATEST(0.0, quality_score + :delta)),
                updated_at = NOW()
            WHERE id = :id
              AND (is_seed = true OR tenant_id = :tenant_id)
        """),
        {"id": case_id, "tenant_id": user.company_id, "delta": delta}
    )

    # If quality dropped below threshold — flag for review
    if not body.positive:
        await db.execute(
            text("""
                UPDATE objection_cases
                SET is_published = CASE
                    WHEN quality_score < 0.3 THEN false
                    ELSE is_published
                END
                WHERE id = :id
            """),
            {"id": case_id}
        )

    await db.commit()
    return {"status": "ok", "new_quality_score_updated_by": delta}


# ============================================================================
# 5. Create new case (technologist only)
# ============================================================================

@router.post("/objection-cases", response_model=CaseResponse, status_code=201)
async def create_case(
    body: CreateCaseRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("technologist")),
):
    import hashlib
    content_hash = hashlib.sha256(
        f"{body.objection_text}::{body.response_text}".encode()
    ).hexdigest()[:16]

    case_id = f"usr_{uuid.uuid4().hex[:11]}"

    # Insert into PostgreSQL
    await db.execute(
        text("""
            INSERT INTO objection_cases
                (id, tenant_id, category, category_label,
                 objection_text, response_text, tags,
                 content_hash, is_seed, is_published, created_by)
            VALUES
                (:id, :tenant_id, :category::objection_category, :category_label,
                 :objection_text, :response_text, :tags,
                 :content_hash, :is_seed, true, :user_id)
        """),
        {
            "id": case_id,
            "tenant_id": user.company_id,
            "category": body.category,
            "category_label": body.category_label,
            "objection_text": body.objection_text,
            "response_text": body.response_text,
            "tags": body.tags,
            "content_hash": content_hash,
            "is_seed": body.is_seed,
            "user_id": user.id,
        }
    )
    await db.commit()

    # Index in Qdrant
    await _index_case_in_qdrant(
        case_id=case_id,
        tenant_id=str(user.company_id),
        category=body.category,
        category_label=body.category_label,
        objection_text=body.objection_text,
        response_text=body.response_text,
        tags=body.tags,
        is_seed=body.is_seed,
        car_brand=body.car_brand,
        fluid_type=body.fluid_type,
    )

    return CaseResponse(
        id=case_id, number=None, category=body.category,
        category_label=body.category_label,
        objection_text=body.objection_text,
        response_text=body.response_text,
        tags=body.tags, usage_count=0, quality_score=0.5,
    )


async def _index_case_in_qdrant(
    case_id: str, tenant_id: str, category: str, category_label: str,
    objection_text: str, response_text: str, tags: list[str],
    is_seed: bool, car_brand: Optional[str] = None,
    fluid_type: Optional[str] = None,
):
    """Embed objection_text and store in Qdrant."""
    vector = await embed_text(objection_text)
    qdrant = await get_qdrant()
    point_id = str(uuid.uuid4())

    await qdrant.upsert(
        collection_name=COLLECTION,
        points=[{
            "id": point_id,
            "vector": vector,
            "payload": {
                "case_id": case_id,
                "tenant_id": tenant_id,
                "category": category,
                "category_label": category_label,
                "objection_text": objection_text,
                "response_text": response_text,
                "tags": tags,
                "is_seed": is_seed,
                "is_published": True,
                "car_brand": car_brand,
                "fluid_type": fluid_type,
                "usage_count": 0,
                "quality_score": 0.5,
                "created_at": datetime.utcnow().isoformat(),
            }
        }]
    )

    # Link Qdrant point_id back to PostgreSQL
    # (so we can delete/update Qdrant point when case is updated/deleted)


# ============================================================================
# 6. Bulk import (for seeding 100 cases)
# ============================================================================

class ImportCasesRequest(BaseModel):
    cases: list[CreateCaseRequest]


@router.post("/objection-cases/import")
async def bulk_import(
    body: ImportCasesRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("technologist", "admin")),
):
    imported, skipped, errors = 0, 0, []
    for i, case in enumerate(body.cases):
        try:
            import hashlib
            content_hash = hashlib.sha256(
                f"{case.objection_text}::{case.response_text}".encode()
            ).hexdigest()[:16]
            case_id = case.id if hasattr(case, 'id') and case.id else f"obj_{i + 1:03d}"

            await db.execute(
                text("""
                    INSERT INTO objection_cases
                        (id, tenant_id, number, category, category_label,
                         objection_text, response_text, tags,
                         content_hash, is_seed, is_published)
                    VALUES
                        (:id, :tenant_id, :number, :category::objection_category,
                         :category_label, :objection_text, :response_text,
                         :tags, :content_hash, :is_seed, true)
                    ON CONFLICT (tenant_id, content_hash) DO NOTHING
                """),
                {
                    "id": case_id,
                    "tenant_id": user.company_id if not case.is_seed else uuid.UUID(int=0),
                    "number": i + 1,
                    "category": case.category,
                    "category_label": case.category_label,
                    "objection_text": case.objection_text,
                    "response_text": case.response_text,
                    "tags": case.tags,
                    "content_hash": content_hash,
                    "is_seed": case.is_seed,
                }
            )
            imported += 1
        except Exception as e:
            errors.append({"index": i, "error": str(e)})
            skipped += 1
    await db.commit()

    # Bulk index in Qdrant
    # (implement with embed_batch for efficiency)

    return {"imported": imported, "skipped": skipped, "errors": errors}


# ============================================================================
# 7. MAIN: Handle objection (LLM + RAG pipeline)
# ============================================================================

@router.post("/handle-objection")
async def handle_objection(
    body: HandleObjectionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Main Sales Copilot endpoint.

    Pipeline:
      1. Semantic search for similar cases (RAG context)
      2. Build LLM prompt with retrieved cases as few-shot examples
      3. Stream 3 responses (rational / empathetic / take-charge)
      4. Log the interaction for analytics

    Returns SSE stream for real-time UX.
    """
    # Step 1: RAG — fetch top-K cases
    search_response = await search_objection_cases(
        request=None,
        q=body.objection,
        category=body.category,
        car_brand=body.car_brand,
        fluid_type=body.fluid_type,
        limit=5,
        min_score=0.55,
        db=db,
        user=user,
    )

    # Step 2: Build system prompt
    system_prompt = _build_system_prompt(search_response.cases, body)

    # Step 3: Stream LLM response via SSE
    async def event_stream():
        full_response = []
        try:
            async for chunk in llm_complete_stream(
                system_prompt=system_prompt,
                user_prompt=body.objection,
                max_tokens=2048,
                temperature=0.7,
            ):
                full_response.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"

            # Log interaction
            await db.execute(
                text("""
                    INSERT INTO sales_interactions
                        (tenant_id, user_id, objection, category,
                         retrieved_case_ids, ai_response, context, client_info, created_at)
                    VALUES
                        (:tenant_id, :user_id, :objection, :category,
                         :case_ids, :response, :context, :client_info, NOW())
                """),
                {
                    "tenant_id": user.company_id,
                    "user_id": user.id,
                    "objection": body.objection,
                    "category": body.category,
                    "case_ids": [c.id for c in search_response.cases],
                    "response": "".join(full_response),
                    "context": body.context,
                    "client_info": json.dumps(body.client_info or {}),
                }
            )
            await db.commit()

            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.exception("handle_objection stream failed")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        }
    )


def _build_system_prompt(cases: list[CaseResponse], body: HandleObjectionRequest) -> str:
    """Build LLM system prompt with RAG context."""
    prompt = """Ты — Sales Copilot в системе GSM (Get Some Motor oil), опытный продавец моторных масел B2B.

Твоя задача: дать менеджеру 3 варианта ответа на возражение клиента.

ВАЖНО:
1. Каждый ответ должен быть конкретным, с реальными цифрами/спецификациями (используй кейсы ниже как опору).
2. Не копируй кейсы дословно — адаптируй под контекст клиента.
3. Все три ответа должны быть РАЗНЫМИ по тональности:
   - **1. Рациональный** — цифры, факты, расчёт окупаемости
   - **2. Эмпатичный** — понимание, мягкая альтернатива
   - **3. Перехват инициативы** — закрытие на следующее действие

ФОРМАТ ОТВЕТА (строго):

### 1. Рациональный
[Текст ответа 3-5 предложений]

### 2. Эмпатичный
[Текст ответа 3-5 предложений]

### 3. Перехват инициативы
[Текст ответа 3-5 предложений]

---
"""

    if cases:
        prompt += "\n## 📚 Релевантные кейсы из базы знаний GSM\n\n"
        for i, c in enumerate(cases, 1):
            prompt += f"### Кейс {i} (категория: {c.category_label})\n"
            prompt += f"**Возражение:** {c.objection_text}\n"
            prompt += f"**Проверенный ответ:** {c.response_text}\n\n"

    if body.client_info:
        prompt += f"\n## 👤 Контекст клиента\n{json.dumps(body.client_info, ensure_ascii=False)}\n"

    if body.context:
        prompt += f"\n## 💬 Предыдущий диалог\n{body.context}\n"

    if body.car_brand or body.fluid_type:
        prompt += "\n## 🔧 Спецификация запроса\n"
        if body.car_brand:
            prompt += f"- Бренд авто: {body.car_brand}\n"
        if body.fluid_type:
            prompt += f"- Тип масла: {body.fluid_type}\n"

    prompt += "\n---\n\nСгенерируй 3 варианта ответа на возражение ниже."
    return prompt
