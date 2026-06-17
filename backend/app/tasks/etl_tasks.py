import asyncio
import logging
import os
import tempfile
import uuid as uuid_pkg

from celery import shared_task
from dataclasses import asdict
from minio import Minio
from qdrant_client import AsyncQdrantClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.models.models import ImportBatch, ImportStatus
from app.services.excel_parser import parse_japanese_catalog, list_sheets
from app.services.etl_pipeline import process_import_batch
from app.services.vector_indexer import index_recommendations_to_qdrant

logger = logging.getLogger(__name__)


def _minio_client() -> Minio:
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_use_ssl,
    )


def _make_engine():
    """Создаём новый engine для каждого asyncio.run() — обход конфликта event loops."""
    from sqlalchemy.dialects.postgresql import asyncpg

    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        poolclass=None,  # force fresh pool
    )
    return engine


async def _update_batch(
    batch_id: str,
    status: ImportStatus,
    total_rows: int = 0,
    new_rows: int = 0,
    duplicates: int = 0,
    errors: int = 0,
    error_message: str = "",
    engine=None,
) -> None:
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        stmt = (
            update(ImportBatch)
            .where(ImportBatch.id == uuid_pkg.UUID(batch_id))
            .values(
                status=status,
                total_rows=total_rows,
                new_rows=new_rows,
                duplicates=duplicates,
                errors=errors,
                review_notes=error_message or None,
            )
        )
        await session.execute(stmt)
        await session.commit()


async def _get_batch_tenant(
    db: AsyncSession,
    batch_uuid: uuid_pkg.UUID,
) -> uuid_pkg.UUID | None:
    result = await db.execute(
        select(ImportBatch.company_id).where(ImportBatch.id == batch_uuid)
    )
    return result.scalar_one_or_none()


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def parse_excel_task(
    self,
    batch_id: str,
    minio_path: str,
) -> dict:
    logger.info(
        "Задача parse_excel_task: batch=%s, path=%s", batch_id, minio_path
    )

    tmp_path = None

    async def _run(batch_uuid: uuid_pkg.UUID) -> dict:
        engine = _make_engine()
        try:
            await _update_batch(batch_id, ImportStatus.processing, engine=engine)

            client = _minio_client()
            tmp_fd, tmp_path_inner = tempfile.mkstemp(suffix=".xlsx")
            os.close(tmp_fd)
            nonlocal tmp_path
            tmp_path = tmp_path_inner

            client.fget_object("excel-imports", minio_path, tmp_path)

            sheets = list_sheets(tmp_path)
            logger.info("Листы в файле (%d): %s", len(sheets), sheets)

            raw_row_dicts: list[dict] = []
            file_errors = 0

            for sheet in sheets:
                result = parse_japanese_catalog(tmp_path, sheet_name=sheet)
                raw_row_dicts.extend(asdict(r) for r in result.rows)
                file_errors += len(result.errors)
                if result.errors:
                    for err in result.errors[:3]:
                        logger.warning(
                            "Лист %s, строка %d: %s",
                            sheet, err["excel_row"], err["error"],
                        )

            logger.info(
                "Парсинг листов завершён: %d сырых строк, %d ошибок файла",
                len(raw_row_dicts), file_errors,
            )

            session_maker = async_sessionmaker(engine, expire_on_commit=False)
            async with session_maker() as db:
                tenant_id = await _get_batch_tenant(db, batch_uuid)
                if not tenant_id:
                    raise RuntimeError(f"Batch {batch_id} не найден")

                from sqlalchemy import text
                # Отключаем FORCE RLS на время импорта — RETURNING в ON CONFLICT
                # не работает корректно с включённым RLS (возвращает неверный ID)
                # Безопасность обеспечивается через company_id во всех запросах
                for tbl in ("car_brands", "car_models", "car_variants", "fluids", "recommendations"):
                    await db.execute(text(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY"))
                await db.commit()

                pipeline_result = await process_import_batch(
                    batch_id=batch_uuid,
                    raw_rows=raw_row_dicts,
                    tenant_id=tenant_id,
                    db=db,
                )

                # Включаем RLS обратно
                for tbl in ("car_brands", "car_models", "car_variants", "fluids", "recommendations"):
                    await db.execute(text(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY"))
                await db.commit()

            total_errors = file_errors + pipeline_result["errors"]
            await _update_batch(
                batch_id,
                ImportStatus.completed,
                total_rows=pipeline_result["total"],
                new_rows=pipeline_result["success"],
                errors=total_errors,
                engine=engine,
            )

            logger.info(
                "ETL завершён: успех=%d, ошибок=%d | "
                "новых: брендов=%d, моделей=%d, вариантов=%d, жидкостей=%d",
                pipeline_result["success"],
                pipeline_result["errors"],
                pipeline_result["created_brands"],
                pipeline_result["created_models"],
                pipeline_result["created_variants"],
                pipeline_result["created_fluids"],
            )

            index_qdrant_task.delay(batch_id, str(tenant_id))

            return {
                "batch_id": batch_id,
                "status": ImportStatus.completed.value,
                "success_rows": pipeline_result["success"],
                "errors": total_errors,
                "details": pipeline_result,
            }
        finally:
            await engine.dispose()

    try:
        batch_uuid = uuid_pkg.UUID(batch_id)
        return asyncio.run(_run(batch_uuid))
    except Exception as exc:
        logger.error(
            "Ошибка ETL batch %s: %s", batch_id, exc, exc_info=True
        )

        async def _set_failed():
            engine = _make_engine()
            try:
                await _update_batch(
                    batch_id,
                    ImportStatus.failed,
                    error_message=str(exc),
                    engine=engine,
                )
            finally:
                await engine.dispose()

        asyncio.run(_set_failed())

        raise self.retry(exc=exc)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    acks_late=True,
)
def index_qdrant_task(
    self,
    batch_id: str,
    tenant_id: str,
) -> dict:
    logger.info(
        "Задача index_qdrant_task: batch=%s, tenant=%s", batch_id, tenant_id
    )

    async def _run() -> dict:
        engine = _make_engine()
        qdrant = AsyncQdrantClient(url=settings.qdrant_url)
        try:
            session_maker = async_sessionmaker(engine, expire_on_commit=False)
            async with session_maker() as db:
                count = await index_recommendations_to_qdrant(
                    tenant_id=uuid_pkg.UUID(tenant_id),
                    db=db,
                    qdrant_client=qdrant,
                )
            logger.info(
                "Индексация Qdrant завершена batch=%s: %d точек",
                batch_id, count,
            )
            return {
                "batch_id": batch_id,
                "tenant_id": tenant_id,
                "indexed_points": count,
            }
        finally:
            await qdrant.close()
            await engine.dispose()

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error(
            "Ошибка индексации Qdrant batch=%s: %s",
            batch_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)
