import json
import logging
from typing import AsyncGenerator
from uuid import UUID

from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

from app.core.config import settings
from app.schemas.sales_schemas import ObjectionRequest, ObjectionVariant
from app.services.sales_indexer import _sales_collection
from app.services.vector_indexer import get_embedding_model

logger = logging.getLogger(__name__)

VARIANT_STYLES = [
    {"style": "empathic", "label": "Эмпатичный"},
    {"style": "rational", "label": "Рациональный"},
    {"style": "assertive", "label": "Перехват инициативы"},
]

FALLBACK_RESPONSES: list[ObjectionVariant] = [
    ObjectionVariant(
        style="empathic",
        label="Эмпатичный",
        text="Я понимаю ваше сомнение. Многие клиенты сначала думают так же. "
        "Давайте я покажу вам расчёт экономии на конкретном примере — это займёт 2 минуты.",
    ),
    ObjectionVariant(
        style="rational",
        label="Рациональный",
        text="Давайте посмотрим на цифры: стоимость литра нашего масла при оптовой закупке "
        "на 15% ниже при вдвое большем интервале замены. Итоговая экономия на 10 машин — "
        "более 120 000 ₽ в год.",
    ),
    ObjectionVariant(
        style="assertive",
        label="Перехват инициативы",
        text="Коллеги, давайте я оставлю вам пробники и техническую документацию. "
        "Вы проведёте тест на вашем парке — если результат не устроит, мы заберём "
        "продукт без каких-либо обязательств.",
    ),
]


# =============================================================
# Поиск релевантных кейсов в Qdrant
# =============================================================


async def _search_relevant_cases(
    objection_text: str,
    tenant_id: UUID,
    qdrant: AsyncQdrantClient,
) -> list[dict]:
    collection = _sales_collection(tenant_id)

    try:
        collections = await qdrant.get_collections()
        if collection not in [c.name for c in collections.collections]:
            logger.warning("Коллекция %s не найдена", collection)
            return []
    except Exception:
        logger.warning("Не удалось получить коллекцию %s", collection)
        return []

    model = get_embedding_model()
    query_vector = model.encode(objection_text).tolist()

    try:
        results = await qdrant.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=3,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="tenant_id",
                        match=MatchValue(value=str(tenant_id)),
                    ),
                ]
            ),
        )
    except Exception as exc:
        logger.warning("Ошибка поиска в Qdrant: %s", exc)
        return []

    return [r.payload for r in results if r.payload]


# =============================================================
# Генерация ответа через LLM (потоковая)
# =============================================================


async def _stream_llm_response(
    objection_text: str,
    context: str | None,
    rag_cases: list[dict],
) -> AsyncGenerator[str, None]:
    prompt = _build_prompt(objection_text, context, rag_cases)

    client = AsyncOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
    )

    stream = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты — эксперт по B2B-продажам моторных масел и технических жидкостей. "
                    "Клиент высказал возражение. Твоя задача — сгенерировать СТРОГО 3 варианта ответа:\n"
                    "1. Эмпатичный — понимание и мягкое переубеждение.\n"
                    "2. Рациональный — цифры, факты, расчёты.\n"
                    "3. Перехват инициативы — предложение действия (тест, пробник, встреча).\n\n"
                    "Формат ответа (каждый вариант с новой строки):\n"
                    "## Эмпатичный\nтекст...\n"
                    "## Рациональный\nтекст...\n"
                    "## Перехват инициативы\nтекст..."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        stream=True,
        temperature=0.7,
        max_tokens=800,
    )

    async for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content


def _build_prompt(
    objection_text: str,
    context: str | None,
    rag_cases: list[dict],
) -> str:
    lines = [f"Клиент возразил: {objection_text}"]
    if context:
        lines.append(f"Контекст: {context}")

    if rag_cases:
        lines.append("\nУспешные кейсы из базы знаний компании:")
        for i, case in enumerate(rag_cases, 1):
            cat = case.get("category", "Общее")
            arg = case.get("core_argument", "")
            reply = case.get("successful_reply", "")
            lines.append(f"{i}. [{cat}] Аргумент: {arg}. Ответ: {reply}")

    return "\n".join(lines)


# =============================================================
# Парсинг ответа LLM в структурированные варианты
# =============================================================


def _parse_llm_response(text: str) -> list[ObjectionVariant]:
    variants: list[ObjectionVariant] = []
    sections = {"## Эмпатичный": "empathic", "## Рациональный": "rational", "## Перехват инициативы": "assertive"}
    labels = {"## Эмпатичный": "Эмпатичный", "## Рациональный": "Рациональный", "## Перехват инициативы": "Перехват инициативы"}

    current_style = None
    current_label = None
    current_text: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if stripped in sections:
            if current_style and current_text:
                variants.append(ObjectionVariant(
                    style=current_style,
                    label=current_label or "",
                    text="\n".join(current_text).strip(),
                ))
            current_style = sections[stripped]
            current_label = labels.get(stripped, stripped.replace("## ", ""))
            current_text = []
        elif current_style:
            current_text.append(stripped)

    if current_style and current_text:
        variants.append(ObjectionVariant(
            style=current_style,
            label=current_label or "",
            text="\n".join(current_text).strip(),
        ))

    return variants


# =============================================================
# Основная функция — потоковая обработка возражения
# =============================================================


async def stream_objection_response(
    request: ObjectionRequest,
    tenant_id: UUID,
    qdrant: AsyncQdrantClient,
) -> AsyncGenerator[str, None]:
    rag_cases = await _search_relevant_cases(
        request.objection_text, tenant_id, qdrant,
    )

    # Поток SSE: сначала мета-событие с информацией, потом чанки текста
    meta = json.dumps({
        "type": "meta",
        "rag_cases_found": len(rag_cases),
    })
    yield f"data: {meta}\n\n"

    full_text = ""
    try:
        async for chunk in _stream_llm_response(
            request.objection_text,
            request.context,
            rag_cases,
        ):
            full_text += chunk
            payload = json.dumps({"type": "chunk", "text": chunk})
            yield f"data: {payload}\n\n"
    except Exception as exc:
        logger.error("Ошибка LLM: %s", exc)
        # Fallback: отправляем заготовки
        fallback_payload = json.dumps({"type": "fallback", "reason": str(exc)})
        yield f"data: {fallback_payload}\n\n"
        full_text = ""

    if full_text:
        variants = _parse_llm_response(full_text)
    else:
        variants = FALLBACK_RESPONSES

    done = json.dumps({
        "type": "done",
        "variants": [v.model_dump() for v in variants],
    })
    yield f"data: {done}\n\n"
    yield "data: [DONE]\n\n"
