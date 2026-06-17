# TEMPLATES.md — Шаблоны для стандартизации кода

## 1. Шаблон нового доменного модуля

```text
backend/app/domains/{domain_name}/
├── __init__.py
├── models.py       # SQLAlchemy 2.0 модели
├── schemas.py      # Pydantic V2 схемы
├── router.py       # FastAPI роутер
└── service.py      # Бизнес-логика
```

---

## 2. Шаблон FastAPI роутера

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session

router = APIRouter(prefix="/api/v1/{entity}", tags=["{Entity}"])


@router.get("/")
async def list_(
    session: AsyncSession = Depends(get_db_session),
):
    """Получить список {entity}."""
    ...


@router.get("/{entity_id}")
async def get(
    entity_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
):
    """Получить {entity} по ID."""
    ...
```

---

## 3. Шаблон Pydantic схемы

```python
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime


class EntityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class EntityCreate(BaseModel):
    name: str
    ...


class EntityUpdate(BaseModel):
    name: str | None = None
    ...
```

---

## 4. Шаблон SQLAlchemy модели

```python
import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class Entity(Base, TimestampMixin):
    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    company = relationship("Company", back_populates="entities")
```

---

## 5. Шаблон ETL-сервиса

```python
import pandas as pd
from uuid import UUID


async def parse_excel_file(file_path: str, company_id: UUID) -> list[dict]:
    """Парсит Excel-файл и возвращает список сырых строк."""
    df = pd.read_excel(file_path, header=[0, 1])
    # Forward-fill объединённых ячеек
    df = df.ffill(axis=0)
    rows = df.to_dict(orient="records")
    return rows
```

---

## 6. Шаблон Celery задачи

```python
from celery import Celery

celery_app = Celery("oil_expert", broker=settings.redis_url)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_import(self, batch_id: str):
    """Фоновая обработка импортированного файла."""
    try:
        ...
    except Exception as exc:
        self.retry(exc=exc)
```
