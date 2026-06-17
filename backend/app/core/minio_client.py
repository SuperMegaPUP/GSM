import logging

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

logger = logging.getLogger(__name__)

minio_client = Minio(
    endpoint=settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_use_ssl,
)


async def ensure_bucket_exists() -> None:
    bucket = "excel-imports"
    try:
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
            logger.info("Бакет '%s' создан", bucket)
        else:
            logger.info("Бакет '%s' уже существует", bucket)
    except S3Error as exc:
        logger.error("Ошибка при создании бакета '%s': %s", bucket, exc)
        raise
