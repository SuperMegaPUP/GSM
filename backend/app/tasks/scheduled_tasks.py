import asyncio
import logging

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models.models import Company
from app.services.billing_service import (
    check_and_update_subscriptions,
    suspend_expired,
)
from app.services.predictive_analytics import generate_daily_action_plan

logger = logging.getLogger(__name__)


def _make_engine():
    from sqlalchemy.ext.asyncio import create_async_engine
    return create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=2,
        max_overflow=4,
        pool_pre_ping=True,
    )


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def check_subscriptions_task(self):
    """Ежедневная проверка: ACTIVE → GRACE_PERIOD если end_date истёк."""
    logger.info("Запуск check_subscriptions_task")

    async def _run():
        engine = _make_engine()
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as db:
            count = await check_and_update_subscriptions(db)
            logger.info("Переведено в GRACE_PERIOD: %d", count)

        await engine.dispose()

    asyncio.run(_run())


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def suspend_expired_task(self):
    """Ежечасная проверка: GRACE_PERIOD → SUSPENDED если grace_period истёк."""
    logger.info("Запуск suspend_expired_task")

    async def _run():
        engine = _make_engine()
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as db:
            count = await suspend_expired(db)
            logger.info("Переведено в SUSPENDED: %d", count)

        await engine.dispose()

    asyncio.run(_run())


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def predictive_analytics_task(self):
    """Ежедневная генерация плана действий для всех компаний."""
    logger.info("Запуск predictive_analytics_task")

    async def _run():
        engine = _make_engine()
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_maker() as db:
                result = await db.execute(select(Company.id))
                companies = result.scalars().all()
                logger.info("Генерация планов для %d компаний", len(companies))

                for cid in companies:
                    try:
                        await generate_daily_action_plan(cid, db)
                    except Exception as exc:
                        logger.warning(
                            "Ошибка генерации плана company=%s: %s",
                            cid, exc, exc_info=True,
                        )
        finally:
            await engine.dispose()

    asyncio.run(_run())
