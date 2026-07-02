import asyncio
import json
import logging
from datetime import date, datetime, timezone
from uuid import UUID

from celery import shared_task
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models.analytics import DailyTrend
from app.models.models import Company
from app.services.billing_service import (
    check_and_update_subscriptions,
    suspend_expired,
)
from app.services.predictive_analytics import generate_daily_action_plan

logger = logging.getLogger(__name__)


def _make_engine():
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


async def _compute_trends_for_company(cid: UUID, db):
    """Compute daily trends for a single company."""
    today = date.today()

    # Trend 1: objections_total — всего возражений за сегодня
    result = await db.execute(
        select(func.count(text("*")))
        .select_from(text("sales_interactions"))
        .where(text("tenant_id = :cid AND created_at::date = :today"))
        .params(cid=cid, today=today)
    )
    total = result.scalar() or 0

    val_json = json.dumps({"count": total})
    await db.execute(
        text("""
            INSERT INTO daily_trends (company_id, date, metric, value)
            VALUES (:cid, :today, 'objections_total', CAST(:val AS jsonb))
            ON CONFLICT (company_id, date, metric)
            DO UPDATE SET value = CAST(:val AS jsonb), updated_at = NOW()
        """),
        {"cid": cid, "today": today, "val": val_json},
    )

    # Trend 2: objections_by_category — группировка по категориям
    result = await db.execute(
        select(
            text("COALESCE(category, 'unknown') AS cat"),
            func.count(text("*")).label("cnt"),
        )
        .select_from(text("sales_interactions"))
        .where(text("tenant_id = :cid AND created_at::date = :today"))
        .group_by(text("cat"))
        .params(cid=cid, today=today)
    )
    cat_data = {r.cat: r.cnt for r in result.all()}

    cat_json = json.dumps(cat_data)
    await db.execute(
        text("""
            INSERT INTO daily_trends (company_id, date, metric, value)
            VALUES (:cid, :today, 'objections_by_category', CAST(:val AS jsonb))
            ON CONFLICT (company_id, date, metric)
            DO UPDATE SET value = CAST(:val AS jsonb), updated_at = NOW()
        """),
        {"cid": cid, "today": today, "val": cat_json},
    )

    # Trend 3: case_stats — сводка по кейсам
    result = await db.execute(
        select(
            func.coalesce(func.sum(text("usage_count")), 0).label("total_used"),
            func.coalesce(func.sum(text("success_count")), 0).label("total_won"),
            func.coalesce(func.sum(text("failure_count")), 0).label("total_lost"),
            func.count(text("*")).label("total_cases"),
        )
        .select_from(text("objection_cases"))
        .where(text("is_published = true"))
    )
    row = result.one()

    stats_json = json.dumps({
        "total_used": row.total_used,
        "total_won": row.total_won,
        "total_lost": row.total_lost,
        "total_cases": row.total_cases,
        "success_rate": round(
            row.total_won / (row.total_won + row.total_lost or 1), 3
        ),
    })
    await db.execute(
        text("""
            INSERT INTO daily_trends (company_id, date, metric, value)
            VALUES (:cid, :today, 'case_stats', CAST(:val AS jsonb))
            ON CONFLICT (company_id, date, metric)
            DO UPDATE SET value = CAST(:val AS jsonb), updated_at = NOW()
        """),
        {"cid": cid, "today": today, "val": stats_json},
    )

    await db.commit()


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def compute_trends_task(self):
    """Ночная агрегация трендов для всех компаний."""
    logger.info("Запуск compute_trends_task")

    async def _run():
        engine = _make_engine()
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_maker() as db:
                result = await db.execute(select(Company.id))
                companies = result.scalars().all()
                logger.info("Агрегация трендов для %d компаний", len(companies))
                for cid in companies:
                    try:
                        await _compute_trends_for_company(cid, db)
                    except Exception as exc:
                        logger.warning(
                            "Ошибка трендов company=%s: %s",
                            cid, exc, exc_info=True,
                        )
                        await db.rollback()
        finally:
            await engine.dispose()

    asyncio.run(_run())
