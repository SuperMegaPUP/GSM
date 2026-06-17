import io
import uuid as uuid_pkg

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.minio_client import minio_client
from app.tasks.etl_tasks import parse_excel_task
from app.models.models import ImportBatch, ImportStatus
from app.schemas.etl_schemas import ImportBatchResponse
from app.core.dependencies import get_current_active_user
from app.models.models import User

router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


@router.post("/upload", response_model=ImportBatchResponse, status_code=201)
async def upload_excel(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_active_user),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть в формате .xlsx",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пустой файл",
        )

    file_uuid = uuid_pkg.uuid4()
    minio_path = f"{current_user.company_id}/{file_uuid}.xlsx"

    try:
        await _upload_to_minio(content, minio_path, file.content_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сохранения файла в хранилище: {exc}",
        )

    batch = ImportBatch(
        filename=file.filename,
        uploaded_by=current_user.id,
        company_id=current_user.company_id,
        status=ImportStatus.pending,
    )
    session.add(batch)
    await session.commit()
    await session.refresh(batch)

    parse_excel_task.delay(str(batch.id), minio_path)

    return batch


async def _upload_to_minio(content: bytes, object_path: str, content_type: str) -> None:
    import asyncio
    await asyncio.to_thread(
        minio_client.put_object,
        "excel-imports",
        object_path,
        io.BytesIO(content),
        len(content),
        content_type=content_type,
    )
