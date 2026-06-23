import json
import logging
import uuid
from typing import AsyncGenerator, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.hybrid_search import hybrid_search
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

VARIANT_DEFS = [
    ("rational", "🧠 РАЦИОНАЛЬНЫЙ",
     "ЦИФРЫ, факты, расчёт ROI, технические параметры, экономия."),
    ("empathetic", "🤝 ЭМПАТИЧНЫЙ",
     "начни с понимания позиции клиента, предложи мягкую альтернативу."),
    ("take_charge", "⚡ ПЕРЕХВАТ ИНИЦИАТИВЫ",
     "закрой на следующее действие, задай встречный вопрос, предложи тест."),
]

SYSTEM_PROMPT_TEMPLATE = """Ты — Sales Copilot в системе GSM (Get Some Motor oil), опытный продавец моторных масел B2B.

Твоя задача — дать ОДИН вариант ответа на возражение клиента в указанном стиле.

ВАЖНО:
1. Используй кейсы из базы знаний как опору, НЕ копируй дословно.
2. Подставляй реальные данные из контекста (бренд авто, тип масла).
3. Ответ 3-5 предложений, конкретные факты и цифры.
4. В конце — call-to-action.

## Релевантные кейсы из базы знаний GSM
{cases_context}

## ТЕКУЩИЙ ВАРИАНТ: {variant_label}
Стиль: {style_hint}

Возражение клиента: "{objection}"

Сгенерируй ответ в стиле {variant_label}. Только текст ответа, без заголовков."""


async def sales_copilot_stream(
    objection: str,
    tenant_id: UUID,
    db: AsyncSession,
    *,
    category: Optional[str] = None,
    car_brand: Optional[str] = None,
    fluid_type: Optional[str] = None,
    context_chips: Optional[list] = None,
) -> AsyncGenerator[str, None]:

    # 1. Hybrid search
    try:
        search_result = await hybrid_search(
            query=objection,
            tenant_id=tenant_id,
            db=db,
            category=category,
            car_brand=car_brand,
            fluid_type=fluid_type,
            limit=5,
            min_score=0.55,
            use_reranker=True,
        )
        cases = search_result["cases"]
        logger.info(
            "Hybrid search: %d cases, method=%s, latency=%dms",
            len(cases), search_result["search_method"], search_result["latency_ms"],
        )
    except Exception as e:
        logger.exception("Hybrid search failed")
        yield _sse("error", {"message": f"Поиск кейсов не удался: {e}"})
        return

    # 2. RAG indicator event (FIRST, before LLM)
    rag_cases_payload = [
        {
            "case_id": c["id"],
            "score": c.get("score", 0.5),
            "category": c.get("category", ""),
            "category_label": c.get("category_label", ""),
            "objection_text": c.get("objection_text", ""),
            "search_method": search_result["search_method"],
        }
        for c in cases
    ]
    yield _sse("rag_cases", {"cases": rag_cases_payload})

    if not cases:
        yield _sse("error", {"message": "Не найдено релевантных кейсов в базе знаний"})
        return

    # 3. Build cases context
    cases_context = _build_cases_context(cases)

    # 4. Generate 3 variants sequentially
    top_case_ids = [c["id"] for c in cases[:2]]
    llm = LLMClient()

    for variant_key, variant_label, style_hint in VARIANT_DEFS:
        yield _sse("variant_start", {
            "variant": variant_key,
            "case_ids": top_case_ids,
        })

        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            cases_context=cases_context,
            variant_label=variant_label,
            style_hint=style_hint,
            objection=objection,
        )

        variant_text = ""
        try:
            async for chunk in llm.stream_generate(
                prompt=f"Стиль: {variant_label}\n\nВозражение: {objection}",
                system=system_prompt,
            ):
                if chunk:
                    variant_text += chunk
                    yield _sse("variant_chunk", {
                        "variant": variant_key,
                        "chunk": chunk,
                    })
        except Exception as e:
            logger.exception("LLM stream failed for variant %s", variant_key)
            yield _sse("variant_chunk", {
                "variant": variant_key,
                "chunk": f"\n\n[Ошибка генерации: {e}]",
            })

        yield _sse("variant_done", {"variant": variant_key})

    # 5. Log interaction
    try:
        await _log_interaction(db, tenant_id, objection, category, cases)
    except Exception as e:
        logger.warning("Failed to log interaction: %s", e)

    yield _sse("done", {"interaction_id": str(uuid.uuid4())})


def _build_cases_context(cases: list[dict]) -> str:
    lines = []
    for i, c in enumerate(cases[:3], 1):
        lines.append(f"### Кейс {i} (категория: {c.get('category_label', '')})")
        lines.append(f"**Возражение:** {c.get('objection_text', '')}")
        lines.append(f"**Проверенный ответ:** {c.get('response_text', '')}")
        lines.append("")
    return "\n".join(lines)


def _sse(event_type: str, data: dict) -> str:
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _log_interaction(
    db: AsyncSession,
    tenant_id: UUID,
    objection: str,
    category: Optional[str],
    cases: list[dict],
) -> None:
    await db.execute(
        text("""
            INSERT INTO sales_interactions
                (tenant_id, objection, category, retrieved_case_ids, created_at)
            VALUES
                (:tenant_id, :objection, :category, :case_ids, NOW())
        """),
        {
            "tenant_id": tenant_id,
            "objection": objection,
            "category": category,
            "case_ids": [c.get("id") for c in cases],
        },
    )
    await db.commit()
