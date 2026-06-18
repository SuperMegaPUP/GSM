import logging
from uuid import UUID

from redis import asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.models import CarModel, CarVariant, Fluid, Recommendation
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

# =============================================================
# Промпт для AI-эксперта
# =============================================================

SYSTEM_PROMPT = (
    "Ты — эксперт-технолог по моторным маслам и техническим жидкостям. "
    "Отвечай на русском языке кратко и по делу. "
    "Объясни, почему конкретное масло подходит для конкретного автомобиля. "
    "Упомяни вязкость, допуски, спецификации и объём. "
    "Не используй markdown, только обычный текст."
)

CACHE_TTL = 86400  # 24 часа


# =============================================================
# Генерация экспертного пояснения
# =============================================================


async def explain_recommendation(
    fluid_id: UUID,
    car_variant_id: UUID,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> str:
    """Генерирует экспертное пояснение: почему масло подходит для авто.
    
    Проверяет кэш Redis, при промахе вызывает LLM.
    """
    cache_key = f"explain:{fluid_id}:{car_variant_id}"

    # Проверка кэша Redis
    try:
        cached_bytes = await redis.get(cache_key)
        if cached_bytes:
            logger.info("Пояснение из кэша: %s", cache_key)
            return str(cached_bytes)
    except Exception as exc:
        logger.warning("Ошибка чтения Redis: %s", exc)

    # Загрузка данных из БД
    fluid = await _load_fluid(fluid_id, db)
    variant = await _load_variant(car_variant_id, db)

    if not fluid or not variant:
        return "Не удалось загрузить данные о масле или автомобиле."

    # Собираем рекомендацию для этого variant + fluid
    rec = await _load_recommendation(fluid_id, car_variant_id, db)

    # Формируем промпт
    prompt = _build_explain_prompt(fluid, variant, rec)

    # Вызов LLM
    client = LLMClient()
    explanation = await client.generate(prompt=prompt, system=SYSTEM_PROMPT)

    if explanation == "AI-сервис временно недоступен.":
        # Если LLM недоступен, генерируем заглушку на основе данных
        explanation = _build_fallback_explanation(fluid, variant, rec)

    # Сохраняем в кэш (неблокирующая ошибка)
    try:
        await redis.setex(cache_key, CACHE_TTL, explanation)
    except Exception as exc:
        logger.warning("Ошибка записи в Redis: %s", exc)

    return explanation


async def explain_recommendation_cached(
    fluid_id: UUID,
    car_variant_id: UUID,
    db: AsyncSession,
    redis: aioredis.Redis,
) -> tuple[str, bool]:
    """Возвращает (текст пояснения, был ли ответ из кэша)."""
    cache_key = f"explain:{fluid_id}:{car_variant_id}"

    # Проверка кэша
    try:
        cached = await redis.get(cache_key)
        if cached:
            return cached, True
    except Exception:
        pass

    explanation = await explain_recommendation(fluid_id, car_variant_id, db, redis)
    return explanation, False


# =============================================================
# Загрузка данных из БД
# =============================================================


async def _load_fluid(fluid_id: UUID, db: AsyncSession) -> Fluid | None:
    result = await db.execute(
        select(Fluid).where(Fluid.id == fluid_id)
    )
    return result.scalar_one_or_none()


async def _load_variant(variant_id: UUID, db: AsyncSession) -> CarVariant | None:
    result = await db.execute(
        select(CarVariant)
        .options(joinedload(CarVariant.model).joinedload(CarModel.brand))
        .where(CarVariant.id == variant_id)
    )
    return result.unique().scalar_one_or_none()


async def _load_recommendation(
    fluid_id: UUID, variant_id: UUID, db: AsyncSession
) -> Recommendation | None:
    result = await db.execute(
        select(Recommendation).where(
            Recommendation.fluid_id == fluid_id,
            Recommendation.car_variant_id == variant_id,
        )
    )
    return result.scalar_one_or_none()


# =============================================================
# Формирование промпта
# =============================================================


def _build_explain_prompt(
    fluid: Fluid,
    variant: CarVariant,
    rec: Recommendation | None,
) -> str:
    car_model: CarModel = variant.model
    brand_name = car_model.brand.name_ru if car_model.brand else "Неизвестно"

    lines = [
        f"Автомобиль: {brand_name} {car_model.name}",
        f"Код двигателя: {variant.engine_code or 'не указан'}",
        f"Объём двигателя: {variant.engine_volume or 'не указан'} л",
        f"Годы выпуска: {variant.year_start or '?'}–{variant.year_end or '?'}",
        "",
        f"Масло: {fluid.canonical_name}",
        f"Бренд: {fluid.brand or 'не указан'}",
        f"Линейка: {fluid.product_line or 'не указана'}",
        f"Вязкость SAE: {fluid.viscosity_sae or 'не указана'}",
        f"Класс API: {fluid.api_class or 'не указан'}",
        f"Класс ACEA: {fluid.acea_class or 'не указан'}",
        f"OEM-допуски: {', '.join(fluid.oem_approvals) if fluid.oem_approvals else 'не указаны'}",
        f"Тип жидкости: {fluid.fluid_type.value}",
    ]

    if rec:
        lines.append("")
        lines.append(f"Объём заливки: {rec.volume_liters or 'не указан'} л")
        if rec.volume_with_filter:
            lines.append(f"Объём с фильтром: {rec.volume_with_filter} л")
        lines.append(f"OEM-рекомендация: {'да' if rec.is_oem_recommendation else 'нет (аналог)'}")
        if rec.oem_specification:
            lines.append(f"Спецификация: {rec.oem_specification}")

    lines.append("")
    lines.append(
        "Дай краткое экспертное пояснение (2–4 предложения), "
        "почему это масло подходит для данного автомобиля. "
        "Упомяни критические параметры: вязкость, допуски, объём."
    )

    return "\n".join(lines)


# =============================================================
# Fallback-объяснение (без LLM)
# =============================================================


def _build_fallback_explanation(
    fluid: Fluid,
    variant: CarVariant,
    rec: Recommendation | None,
) -> str:
    parts = [
        f"Масло {fluid.canonical_name}",
    ]
    if fluid.viscosity_sae:
        parts.append(f"вязкостью {fluid.viscosity_sae}")
    if fluid.api_class:
        parts.append(f"классом API {fluid.api_class}")
    if fluid.oem_approvals:
        parts.append(f"допусками {', '.join(fluid.oem_approvals)}")

    car_model = variant.model
    brand_name = car_model.brand.name_ru if car_model.brand else ""
    car_desc = f"{brand_name} {car_model.name}".strip()

    if rec and rec.is_oem_recommendation:
        explanation = (
            f"{', '.join(parts)} полностью соответствует заводским "
            f"требованиям для {car_desc}."
        )
    else:
        explanation = (
            f"{', '.join(parts)} является подходящим аналогом "
            f"для {car_desc}."
        )

    if rec and rec.volume_liters:
        explanation += f" Объём заливки: {rec.volume_liters} л."

    return explanation
