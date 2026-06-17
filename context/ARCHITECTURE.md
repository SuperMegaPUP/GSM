# ARCHITECTURE.md — Архитектура проекта GSM

## 1. Общая схема (Lean MVP)

```
┌──────────────────────────────────────────────────────┐
│                    NGINX (Reverse Proxy)              │
│  /api/* → backend:8000  / → frontend:3000            │
└────────────────────┬─────────────────────────────────┘
                     │
┌────────────────────┼─────────────────────────────────┐
│  ┌─────────────────▼──────────────────────────┐      │
│  │         FASTAPI (Modular Monolith)          │      │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐  │      │
│  │  │ Auth     │ │ Billing  │ │ CRUD       │  │      │
│  │  │ (JWT)    │ │(Grace    │ │ Справоч-   │  │      │
│  │  │          │ │ Period)  │ │ ников      │  │      │
│  │  ├──────────┤ ├──────────┤ ├────────────┤  │      │
│  │  │ ETL      │ │ LLM+RAG  │ │ Sales      │  │      │
│  │  │ (Excel)  │ │(Qdrant)  │ │ Copilot    │  │      │
│  │  └──────────┘ └──────────┘ └────────────┘  │      │
│  └─────────────────────────────────────────────┘      │
│                                                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐  │
│  │PostgreSQL│  │  Qdrant  │  │  Redis   │  │MinIO │  │
│  │ +pgvector│  │(векторы) │  │+Celery   │  │(S3)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────┘  │
└──────────────────────────────────────────────────────┘
```

## 2. Сервисы (docker-compose)

| Сервис | Порт | Назначение |
|---|---|---|
| `postgres` | 5432 | Основная БД + pgvector |
| `qdrant` | 6333/6334 | Векторный поиск (RAG) |
| `redis` | 6379 | Кэш + Celery broker |
| `minio` | 9000/9001 | S3-хранилище файлов |
| `backend` | 8000 | FastAPI + Celery worker |
| `nginx` | 80 | Reverse proxy |

## 3. Структура БД (9 таблиц)

```
companies → users
         → car_brands → car_models → car_variants
         → fluids
         → recommendations (car_variant_id + fluid_id + node_type)
         → import_batches → staging_rows
```

- Multi-tenancy через `company_id` + RLS
- `fluids.oem_approvals` — JSONB для гибких допусков
- `car_variants.source_hash` — дедупликация импортов

## 4. Ролевая модель

| Роль | Права |
|---|---|
| `admin` | Полный доступ, управление компанией |
| `supervisor` | Валидация справочников, управление данными |
| `manager` | Подбор масел, Sales Copilot, просмотр |
| `technologist` | Загрузка/обработка каталогов, ETL |

## 5. API-контракты (ключевые)

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/v1/health` | Healthcheck |
| POST | `/api/v1/auth/login` | JWT-логин |
| POST | `/api/v1/catalog/upload` | Загрузка Excel |
| POST | `/api/v1/catalog/search` | Поиск масел |
| POST | `/api/v1/sales/handle-objection` | Sales Copilot |
