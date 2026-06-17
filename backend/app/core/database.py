import uuid
from datetime import datetime
from contextvars import ContextVar
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, ORMExecuteState, Session, Mapped, mapped_column
from sqlalchemy.sql import Select, Update, Delete

from app.core.config import settings

# =============================================================
# Engine & Session
# =============================================================

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# =============================================================
# Multi-tenancy: контекст текущего tenant_id
# =============================================================

tenant_id_var: ContextVar[uuid.UUID | None] = ContextVar(
    "tenant_id", default=None
)


def set_tenant_id(tenant_id: uuid.UUID) -> None:
    tenant_id_var.set(tenant_id)


def get_tenant_id() -> uuid.UUID | None:
    return tenant_id_var.get()


# =============================================================
# RLS: автоматическая подстановка фильтра company_id
# Через событие do_orm_execute добавляем WHERE company_id = ...
# Это второй уровень защиты (первый — политики RLS в PostgreSQL).
# =============================================================

TENANT_AWARE_TABLES = {
    "users", "car_brands", "car_models", "car_variants",
    "fluids", "recommendations", "import_batches", "staging_rows",
}


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(execute_state: ORMExecuteState) -> None:
    """Автоматически добавляет фильтр company_id только к SELECT.

    INSERT/UPDATE/DELETE уже содержат company_id через TenantAwareMixin,
    а безопасность обеспечивает RLS в PostgreSQL.
    .params() не поддерживается для DML-операторов в SQLAlchemy 2.0.

    Запросы с опцией skip_tenant_filter=True пропускаются.
    """
    tenant_id = tenant_id_var.get()
    if tenant_id is None:
        return

    if not execute_state.is_orm_statement:
        return

    if execute_state.execution_options.get("skip_tenant_filter"):
        return

    statement = execute_state.statement

    # Только для SELECT — DML (INSERT/UPDATE/DELETE) обрабатываются
    # через TenantAwareMixin + RLS политики PostgreSQL
    if isinstance(statement, Select):
        for col_desc in statement.column_descriptions:
            entity = col_desc.get("type", col_desc.get("expr"))
            if entity is None:
                continue
            table_name = getattr(entity, "__tablename__", None)
            if table_name and table_name in TENANT_AWARE_TABLES:
                statement = statement.where(
                    text(f"{table_name}.company_id = :_tenant_id")
                ).params(_tenant_id=str(tenant_id))
                execute_state.statement = statement


# =============================================================
# Базовый класс для моделей SQLAlchemy
# =============================================================

class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Добавляет колонки created_at / updated_at."""

    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
        nullable=False,
    )


# =============================================================
# FastAPI dependency: получение сессии БД с tenant_id
# =============================================================

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency.

    Создаёт сессию, устанавливает tenant_id в PostgreSQL config
    (для RLS-политик) и в contextvar (для ORM-фильтра).
    """
    tenant_id = get_tenant_id()
    async with async_session() as session:
        if tenant_id:
            await session.execute(
                text(
                    f"SELECT set_config('app.current_tenant_id', "
                    f"'{tenant_id}', true)"
                )
            )
        yield session
