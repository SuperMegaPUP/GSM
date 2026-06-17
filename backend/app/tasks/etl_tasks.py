import asyncio
import logging
import os
import tempfile
import uuid as uuid_pkg

from celery import shared_task
from dataclasses import asdict
from minio import Minio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session
from app.models.models import ImportBatch, ImportStatus
from app.services.excel_parser import parse_japanese_catalog, list_sheets
from app.services.etl_pipeline import process_import_batch

logger = logging.getLogger(__name__)


def _minio_client() -> Minio:
    return Minio(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_use_ssl,
    )


async def _update_batch(
    batch_id: str,
    status: ImportStatus,
    total_rows: int = 0,
    new_rows: int = 0,
    duplicates: int = 0,
    errors: int = 0,
    error_message: str = "",
) -> None:
    async with async_session() as session:
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

    try:
        asyncio.run(
            _update_batch(batch_id, ImportStatus.processing)
        )

        client = _minio_client()
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
        os.close(tmp_fd)

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

        batch_uuid = uuid_pkg.UUID(batch_id)

        async def _run_pipeline() -> dict:
            async with async_session() as db:
                tenant_id = await _get_batch_tenant(db, batch_uuid)
                if not tenant_id:
                    raise RuntimeError(f"Batch {batch_id} не найден")

                pipeline_result = await process_import_batch(
                    batch_id=batch_uuid,
                    raw_rows=raw_row_dicts,
                    tenant_id=tenant_id,
                    db=db,
                )
                return pipeline_result

        pipeline_result = asyncio.run(_run_pipeline())

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

        total_errors = file_errors + pipeline_result["errors"]
        asyncio.run(
            _update_batch(
                batch_id,
                ImportStatus.completed,
                total_rows=pipeline_result["success"],
                new_rows=(
                    pipeline_result["created_brands"]
                    + pipeline_result["created_models"]
                    + pipeline_result["created_variants"]
                    + pipeline_result["created_fluids"]
                ),
                errors=total_errors,
            )
        )

        return {
            "batch_id": batch_id,
            "status": ImportStatus.completed.value,
            "success_rows": pipeline_result["success"],
            "errors": total_errors,
            "details": pipeline_result,
        }

    except Exception as exc:
        logger.error(
            "Ошибка ETL batch %s: %s", batch_id, exc, exc_info=True
        )

        try:
            asyncio.run(
                _update_batch(
                    batch_id,
                    ImportStatus.failed,
                    error_message=str(exc),
                )
            )
        except Exception as db_err:
            logger.error(
                "Не удалось обновить статус batch %s: %s", batch_id, db_err
            )

        raise self.retry(exc=exc)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
