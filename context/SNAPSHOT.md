# SNAPSHOT.md — Текущее состояние проекта

**Дата:** 2026-06-17
**Статус:** Этап 2 (SQLAlchemy модели + Pydantic схемы) — ВЫПОЛНЕН

## Что сделано

### Backend (скелет)
- [x] `docker-compose.yml` — 6 сервисов, volumes, healthcheck, логи
- [x] `Dockerfile` — multi-stage, non-root, healthcheck
- [x] `requirements.txt` — 24 зависимости
- [x] `.env.example` — шаблон конфигурации
- [x] `nginx.conf` — reverse proxy (API → backend, UI → frontend)
- [x] `docker/init.sql` — 9 таблиц, ENUMs, RLS, индексы, триггеры, seed
- [x] `app/main.py` — FastAPI app + healthcheck (БД, Redis, Qdrant)
- [x] `app/core/config.py` — Pydantic Settings
- [x] `app/core/database.py` — SQLAlchemy async engine + RLS (do_orm_execute + PostgreSQL RLS)

### Backend (модели + схемы) ✅ Этап 2
- [x] `app/models/models.py` — 9 SQLAlchemy 2.0 моделей (Company, User, CarBrand, CarModel, CarVariant, Fluid, Recommendation, ImportBatch, StagingRow)
- [x] `app/schemas/schemas.py` — 12 Pydantic V2 схем (Auth + Catalog)
- [x] `app/schemas/etl_schemas.py` — 3 Pydantic схемы (RawExcelRow, NormalizedFluid, ImportBatchResponse)
- [x] 5 Python-ENUM классов (UserRole, FluidType, NodeType, SubscriptionStatus, ImportStatus)
- [x] TenantAwareMixin — единообразная изоляция tenant-таблиц

### Контекст проекта
- [x] `context/RULES.md` — Конституция проекта
- [x] `context/ARCHITECTURE.md` — Схема сервисов, БД, API
- [x] `context/BACKLOG.md` — Задачи по этапам
- [x] `context/SNAPSHOT.md` — Этот файл
- [x] `context/WORKLOG.md` — Журнал сессий
- [x] `context/HISTORY.md` — Хроника ключевых решений
- [x] `context/VERSIONING.md` — SemVer
- [x] `context/CONTEXT.md` — Память AI
- [x] `context/RITUALS.md` — 8 ритуалов
- [x] `context/TEMPLATES.md` — Шаблоны кода

### Инфраструктура
- [x] `scripts/start-session.sh` — ритуал начала
- [x] `scripts/update-docs.sh` — ритуал конца
- [x] `.gitignore` — исключены __pycache__, .env, .DS_Store
- [x] `.pre-commit-config.yaml` — Ruff + py_compile
- [x] Git-репозиторий инициализирован
- [x] GitHub repo создан, первый коммит отправлен

## Дерево проекта

```
/home/g/gsm/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── models.py          # 9 ORM-моделей + 5 ENUMs
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py         # Pydantic: Auth + Catalog
│   │   │   └── etl_schemas.py    # Pydantic: ETL/Excel
│   │   └── core/
│   │       ├── __init__.py
│   │       ├── config.py
│   │       └── database.py
│   ├── docker/
│   │   └── init.sql
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── nginx.conf
│   └── requirements.txt
├── context/
│   ├── ARCHITECTURE.md
│   ├── BACKLOG.md
│   ├── CONTEXT.md
│   ├── HISTORY.md
│   ├── RITUALS.md
│   ├── RULES.md
│   ├── SNAPSHOT.md
│   ├── TEMPLATES.md
│   ├── VERSIONING.md
│   └── WORKLOG.md
├── scripts/
│   ├── start-session.sh
│   └── update-docs.sh
├── .gitignore
├── .pre-commit-config.yaml
└── .opencode/
    └── plans/step2-models-schemas.md
```

## Следующая задача

**Этап 3: Backend API (Auth, JWT, мультитенантность)**
- Реализовать Auth: регистрация/логин, JWT, зависимость get_current_user
- Реализовать Middleware: get_tenant_db_session, tenant isolation
- Создать CRUD для справочников
