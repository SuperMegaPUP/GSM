"""
GSM Sales Copilot 2.0 — Hybrid Search Service
================================================

Combines three retrieval signals for best-in-class relevance:

  1. Vector search (Qdrant, named vector "default" = objection_vector)
     - Catches semantic similarity ("дорого" ~ "цена кусается")
     - Fast, but can miss exact keyword matches

  2. Full-text search (PostgreSQL FTS with BM25 ranking via ts_rank)
     - Catches exact term matches (5W-30, SJ, LA-CL7)
     - Strong for technical queries with OEM codes / viscosity

  3. Cross-encoder re-ranking (bge-reranker-base, optional)
     - Re-scores top-20 candidates with a heavier model
     - Radically improves precision for ambiguous queries

Fusion: Reciprocal Rank Fusion (RRF) combines vector + FTS rankings
into a single ordered list, then cross-encoder re-ranks the top-K.

Caching: Embeddings cached in Redis by content_hash (TTL 1h).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.embedding import embed_text
from app.services.qdrant_client import get_qdrant

logger = logging.getLogger(__name__)

# Constants
COLLECTION = "sales_objections"
REDIS_CACHE_TTL = 3600  # 1 hour
VECTOR_TOP_K = 20        # over-fetch for re-ranking
FTS_TOP_K = 20
FINAL_TOP_K = 5
RRF_K = 60              # standard RRF constant


# ============================================================================
# Public API
# ============================================================================

async def hybrid_search(
    query: str,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    *,
    category: Optional[str] = None,
    customer_segment: Optional[str] = None,
    car_brand: Optional[str] = None,
    fluid_type: Optional[str] = None,
    tags: Optional[list[str]] = None,
    limit: int = 5,
    min_score: float = 0.55,
    use_reranker: bool = True,
) -> dict:
    """Hybrid search: vector (Qdrant) + FTS (PostgreSQL) + RRF + re-rank.

    Returns:
        {
            "cases": [{...}],
            "total": int,
            "search_method": "hybrid" | "vector" | "fts",
            "latency_ms": int,
            "components": {
                "vector_hits": int,
                "fts_hits": int,
                "reranked": bool,
            }
        }
    """
    start = time.monotonic()
    components = {"vector_hits": 0, "fts_hits": 0, "reranked": False}

    # Run vector and FTS in parallel
    vector_task = _vector_search(
        query, tenant_id, category, customer_segment,
        car_brand, fluid_type, tags,
    )
    fts_task = _fts_search(
        query, tenant_id, db, category, customer_segment,
        car_brand, fluid_type, tags,
    )

    try:
        vector_results, fts_results = await asyncio.gather(
            vector_task, fts_task, return_exceptions=True
        )
    except Exception as e:
        logger.warning(f"Both searches failed: {e}")
        return _empty_result(query, "fallback", start)

    # Handle individual failures gracefully
    if isinstance(vector_results, Exception):
        logger.warning(f"Vector search failed: {vector_results}")
        vector_results = []
    else:
        components["vector_hits"] = len(vector_results)

    if isinstance(fts_results, Exception):
        logger.warning(f"FTS search failed: {fts_results}")
        fts_results = []
    else:
        components["fts_hits"] = len(fts_results)

    # Determine method
    if vector_results and fts_results:
        method = "hybrid"
    elif vector_results:
        method = "vector"
    elif fts_results:
        method = "fts"
    else:
        return _empty_result(query, "fallback", start)

    # Reciprocal Rank Fusion
    fused = _reciprocal_rank_fusion(vector_results, fts_results)

    # Filter by min_score
    fused = [r for r in fused if r["score"] >= min_score][:limit * 2]

    # Cross-encoder re-ranking (optional, expensive)
    if use_reranker and len(fused) > 1:
        try:
            fused = await _rerank(query, fused)
            components["reranked"] = True
        except Exception as e:
            logger.warning(f"Re-ranker failed, using fused order: {e}")

    # Fetch full case data from PostgreSQL by case_ids
    final_cases = await _fetch_full_cases(
        [r["case_id"] for r in fused[:limit]],
        tenant_id, db
    )

    # Annotate with scores
    score_map = {r["case_id"]: r["score"] for r in fused}
    for c in final_cases:
        c["score"] = score_map.get(c["id"], 0.0)

    latency = int((time.monotonic() - start) * 1000)

    return {
        "cases": final_cases,
        "total": len(final_cases),
        "search_method": method,
        "latency_ms": latency,
        "components": components,
    }


# ============================================================================
# 1. Vector search (Qdrant)
# ============================================================================

async def _vector_search(
    query: str,
    tenant_id: uuid.UUID,
    category: Optional[str],
    customer_segment: Optional[str],
    car_brand: Optional[str],
    fluid_type: Optional[str],
    tags: Optional[list[str]],
) -> list[dict]:
    """Semantic search via Qdrant with payload filters."""

    # Cached embedding
    query_vector = await _cached_embedding(query)

    # Build filter
    must = [
        # Multi-tenant: seed (global) OR own
        {"should": [
            {"key": "is_seed", "match": {"value": True}},
            {"key": "tenant_id", "match": {"value": str(tenant_id)}},
        ]},
        {"key": "is_published", "match": {"value": True}},
        {"key": "needs_review", "match": {"value": False}},
    ]
    if category:
        must.append({"key": "category", "match": {"value": category}})
    if customer_segment:
        must.append({"key": "customer_segment", "match": {"value": customer_segment}})
    if car_brand:
        must.append({"key": "car_brand", "match": {"value": car_brand}})
    if fluid_type:
        must.append({"key": "fluid_type", "match": {"value": fluid_type}})
    if tags:
        must.append({"key": "tags", "match": {"any": tags}})

    qdrant = await get_qdrant()
    hits = await qdrant.search(
        collection_name=COLLECTION,
        query_vector=("default", query_vector),  # named vector
        limit=VECTOR_TOP_K,
        query_filter={"must": must},
        with_payload=True,
        score_threshold=0.3,  # cut off clearly irrelevant
    )

    return [
        {
            "case_id": h.payload.get("case_id"),
            "score": float(h.score),
            "rank_source": "vector",
            "objection_text": h.payload.get("objection_text", ""),
            "response_text": h.payload.get("response_text", ""),
        }
        for h in hits
        if h.payload.get("case_id")
    ]


# ============================================================================
# 2. FTS search (PostgreSQL BM25 via ts_rank)
# ============================================================================

async def _fts_search(
    query: str,
    tenant_id: uuid.UUID,
    db: AsyncSession,
    category: Optional[str],
    customer_segment: Optional[str],
    car_brand: Optional[str],
    fluid_type: Optional[str],
    tags: Optional[list[str]],
) -> list[dict]:
    """Full-text search in PostgreSQL with BM25-style ranking."""

    sql = text("""
        SELECT
            id AS case_id,
            ts_rank(
                to_tsvector('russian',
                    objection_text || ' ' ||
                    coalesce(replace(arguments::text, '"', ''), '') || ' ' ||
                    response_text
                ),
                plainto_tsquery('russian', :q)
            ) AS score,
            objection_text,
            response_text
        FROM objection_cases
        WHERE is_published = true
          AND needs_review = false
          AND (is_seed = true OR tenant_id = :tenant_id)
          AND to_tsvector('russian',
                objection_text || ' ' ||
                coalesce(replace(arguments::text, '"', ''), '') || ' ' ||
                response_text
              ) @@ plainto_tsquery('russian', :q)
          AND (:category IS NULL OR category = :category::objection_category)
          AND (:segment IS NULL OR customer_segment = :segment::customer_segment)
          AND (:car_brand IS NULL OR car_brand = :car_brand)
          AND (:fluid_type IS NULL OR fluid_type = :fluid_type)
        ORDER BY score DESC
        LIMIT :limit
    """)

    rows = await db.execute(sql, {
        "q": query,
        "tenant_id": tenant_id,
        "category": category,
        "segment": customer_segment,
        "car_brand": car_brand,
        "fluid_type": fluid_type,
        "limit": FTS_TOP_K,
    })

    return [
        {
            "case_id": r.case_id,
            "score": float(r.score),
            "rank_source": "fts",
            "objection_text": r.objection_text,
            "response_text": r.response_text,
        }
        for r in rows
    ]


# ============================================================================
# 3. Reciprocal Rank Fusion (RRF)
# ============================================================================

def _reciprocal_rank_fusion(
    vector_results: list[dict],
    fts_results: list[dict],
) -> list[dict]:
    """Combine rankings: score = sum(1 / (k + rank)) for each list.

    Standard RRF with k=60 (Cormack et al., 2009).
    """
    scores: dict[str, float] = {}
    metadata: dict[str, dict] = {}

    for rank, r in enumerate(vector_results, 1):
        cid = r["case_id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank)
        metadata[cid] = r

    for rank, r in enumerate(fts_results, 1):
        cid = r["case_id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (RRF_K + rank)
        if cid not in metadata:
            metadata[cid] = r

    # Sort by fused score, normalize to [0, 1]
    sorted_ids = sorted(scores.items(), key=lambda x: -x[1])
    if not sorted_ids:
        return []

    max_score = sorted_ids[0][1]
    min_score = sorted_ids[-1][1]
    score_range = max_score - min_score if max_score > min_score else 1.0

    return [
        {
            **metadata[cid],
            "case_id": cid,
            "score": (s - min_score) / score_range,  # normalize to [0, 1]
            "fused_score_raw": s,
        }
        for cid, s in sorted_ids
    ]


# ============================================================================
# 4. Cross-encoder re-ranking (optional)
# ============================================================================

_reranker_model = None

async def _rerank(query: str, candidates: list[dict]) -> list[dict]:
    """Re-rank candidates using bge-reranker-base cross-encoder.

    Cross-encoders score (query, document) pairs jointly, giving much
    better precision than bi-encoder cosine similarity. Cost: ~50ms for
    20 documents on CPU.
    """
    global _reranker_model

    if _reranker_model is None:
        # Lazy load — only when first needed
        try:
            from sentence_transformers import CrossEncoder
            _reranker_model = CrossEncoder("BAAI/bge-reranker-base")
        except ImportError:
            logger.warning("sentence-transformers not available, skipping re-ranker")
            return candidates

    # Build (query, doc) pairs — doc = objection + arguments (already in payload)
    pairs = [
        (query, f"{c['objection_text']} {c.get('response_text', '')[:200]}")
        for c in candidates
    ]

    # Run cross-encoder (sync, so offload to thread)
    loop = asyncio.get_event_loop()
    scores = await loop.run_in_executor(
        None,
        lambda: _reranker_model.predict(pairs).tolist()
    )

    # Sort by cross-encoder score (sigmoid output)
    ranked = list(zip(candidates, scores))
    ranked.sort(key=lambda x: -x[1])

    # Normalize scores to [0, 1]
    if ranked:
        max_s = ranked[0][1]
        min_s = ranked[-1][1]
        score_range = max_s - min_s if max_s > min_s else 1.0
        return [
            {**c, "score": (s - min_s) / score_range, "reranked": True}
            for c, s in ranked
        ]
    return candidates


# ============================================================================
# 5. Helpers
# ============================================================================

async def _cached_embedding(text: str) -> list[float]:
    """Cache embeddings in Redis by content hash (TTL 1h)."""
    cache_key = f"emb:{hashlib.sha256(text.encode()).hexdigest()[:16]}"

    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        cached = await redis.get(cache_key)
        if cached:
            await redis.close()
            return json.loads(cached)
        await redis.close()
    except Exception as e:
        logger.debug(f"Redis cache miss: {e}")

    # Compute fresh
    embedding = await embed_text(text)

    # Cache it
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        await redis.setex(cache_key, REDIS_CACHE_TTL, json.dumps(embedding))
        await redis.close()
    except Exception:
        pass  # cache is best-effort

    return embedding


async def _fetch_full_cases(
    case_ids: list[str],
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict]:
    """Fetch full case records from PostgreSQL by IDs, preserving order."""
    if not case_ids:
        return []

    sql = text("""
        SELECT
            id, number, category, category_label, customer_segment,
            objection_text, response_text, arguments, product_context,
            tags, outcome, usage_count, success_count, failure_count,
            last_used_at, is_seed, source, car_brand, fluid_type,
            created_at,
            objection_case_success_rate(objection_cases) AS success_rate,
            objection_case_effective_score(
                success_count, failure_count, usage_count, last_used_at
            ) AS effective_score
        FROM objection_cases
        WHERE id = ANY(:ids)
          AND is_published = true
          AND (is_seed = true OR tenant_id = :tenant_id)
        ORDER BY array_position(:ids, id)
    """)

    rows = await db.execute(sql, {"ids": case_ids, "tenant_id": tenant_id})
    return [
        {
            "id": r.id,
            "number": r.number,
            "category": r.category,
            "category_label": r.category_label,
            "customer_segment": r.customer_segment,
            "objection_text": r.objection_text,
            "response_text": r.response_text,
            "arguments": r.arguments or [],
            "product_context": r.product_context or {},
            "tags": r.tags or [],
            "outcome": r.outcome,
            "usage_count": r.usage_count,
            "success_count": r.success_count,
            "failure_count": r.failure_count,
            "success_rate": float(r.success_rate) if r.success_rate else 0.5,
            "effective_score": float(r.effective_score) if r.effective_score else 0.4,
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            "is_seed": r.is_seed,
            "source": r.source,
            "car_brand": r.car_brand,
            "fluid_type": r.fluid_type,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def _empty_result(query: str, method: str, start: float) -> dict:
    return {
        "cases": [],
        "total": 0,
        "search_method": method,
        "latency_ms": int((time.monotonic() - start) * 1000),
        "components": {"vector_hits": 0, "fts_hits": 0, "reranked": False},
    }
