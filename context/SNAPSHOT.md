# SNAPSHOT.md — Текущее состояние проекта

**Дата:** 2026-06-23
**Статус:** MVP + Sales Copilot 2.0 (RAG-indicator + hybrid search) — 120 seed-кейсов

## Что сделано

### Этап 1: Инфраструктура
- [x] `docker-compose.yml` — 7 сервисов (postgres+pgvector, qdrant, redis, minio, backend, celery-worker, nginx)
- [x] `Dockerfile` — multi-stage, non-root, healthcheck
- [x] `requirements.txt` — 24+ зависимости
- [x] `.env.example` — шаблон конфигурации
- [x] `nginx.conf` — reverse proxy (API → backend, UI → frontend)
- [x] `docker/init.sql` — 9 таблиц, ENUMs, RLS, индексы, триггеры, seed
- [x] `app/main.py` — FastAPI app + healthcheck (БД, Redis, Qdrant, MinIO)
- [x] `app/core/config.py` — Pydantic Settings
- [x] `app/core/database.py` — SQLAlchemy async engine + RLS (do_orm_execute + PostgreSQL RLS)

### Этап 2: Модели + Схемы
- [x] `app/models/models.py` — 9 SQLAlchemy 2.0 моделей (Company, User, CarBrand, CarModel, CarVariant, Fluid, Recommendation, ImportBatch, StagingRow)
- [x] `app/schemas/` — Pydantic V2 схемы для auth, catalog, ETL, search, sales

### Этап 3: Auth + CRUD
- [x] `app/routers/auth.py` — POST /login, POST /register, GET /me (JWT)
- [x] `app/routers/catalog.py` — 10 CRUD endpoints (бренды, модели, варианты, жидкости)
- [x] `app/routers/imports.py` — POST /upload, GET /{id}/status, GET / (list)
- [x] `app/core/security.py` — bcrypt + JWT
- [x] `app/core/dependencies.py` — get_current_active_user (bearer → JWT → tenant_id)
- [x] `app/core/minio_client.py` — MinIO client + ensure_bucket_exists()
- [x] `app/core/celery_app.py` — Celery with Redis broker
- [x] `app/services/crud.py` — async list/create/update/get с tenant_id, ilike, pagination

### Этап 4: ETL-пайплайн
- [x] `app/services/excel_parser.py` — двухуровневый pd.read_excel(header=[0,1])
- [x] `app/services/normalizer.py` — FluidNormalizer, normalize_years, compute_variant_hash
- [x] `app/services/etl_pipeline.py` — process_import_batch с per-row savepoints
- [x] `app/tasks/etl_tasks.py` — parse_excel_task + index_qdrant_task (fresh engine per asyncio.run())
- [x] Импортировано: **11,141 rows**, 8 брендов, 378 моделей, 2,236 вариантов, 270 жидкостей
- [x] Миграция БД: composite UNIQUE constraints для ON CONFLICT

### Этап 5: Гибридный поиск (SQL + Qdrant)
- [x] `app/services/vector_indexer.py` — sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2)
- [x] `app/services/search_engine.py` — SQL + Qdrant fallback, поиск по ВСЕМ моделям
- [x] `app/routers/search.py` — POST /api/v1/search/oils с JWT

### Этап 6: Sales Copilot 2.0 (RAG + LLM + hybrid search)
- [x] `app/services/sales_copilot.py` — RAG + LLM prompt + SSE streaming, 3 варианта (последовательно)
- [x] `app/services/hybrid_search.py` — Vector + FTS + RRF + cross-encoder (исправлен FTS + rollback)
- [x] `app/services/embedding.py` — обёртка эмбеддингов (OpenAI-совместимые)
- [x] `app/services/qdrant_client.py` — Qdrant client singleton (AsyncQdrantClient v2, `.query_points()`)
- [x] `app/routers/sales_copilot.py` — POST /handle-objection (SSE), POST /feedback, GET /cases, GET /stats
- [x] `app/schemas/sales_schemas.py` — Pydantic схемы (min_length=1)
- [x] `context/SALES_COPILOT_SUMMARY.md` — полный свод
- [x] **100 seed-кейсов** (7 категорий) в PostgreSQL + Qdrant (named vectors "default" + "response")
- [x] **+20 seed-кейсов** storage + harmful (120 total) — добавлены 2026-06-23

### Этап 7: Frontend (Next.js 14 + Docker)
- [x] shadcn/ui v4, Zustand, Axios, JWT-перехватчик, Pydantic error normalisation
- [x] Login, Dashboard layout (Sidebar + TopNav), search, imports, sales-copilot
- [x] Search: фильтры по бренду/модели/году/двигателю, результаты по node_type, модель-селектор
- [x] Imports: Drag&Drop загрузка, polling прогресса, история из API
- [x] Sales Copilot Chat (новый): `SalesCopilotChat.tsx` (874 строки, SSE, 3 варианта, копирование, фидбек)
- [x] Sales Copilot (старый): `SalesCopilot.tsx` + `sse-client.ts` — используется на странице поиска масел
- [x] Docker-контейнер `oil-frontend` на сети `backend_default` (Nginx upstream)
- [x] Исправления: `API_URL` вместо `NEXT_PUBLIC_API_URL`, token key `access_token`, `min_length=1`, 422 `objection`

### Контекст проекта
- [x] `context/` — 10 .md файлов (RULES, ARCHITECTURE, BACKLOG, SNAPSHOT, WORKLOG, HISTORY, VERSIONING, CONTEXT, RITUALS, TEMPLATES)
- [x] `scripts/start-session.sh` и `update-docs.sh`
- [x] `.gitignore`, `.pre-commit-config.yaml` (ruff, mypy)
- [x] `backend/requirements-dev.txt` — ruff, mypy, types-PyYAML
- [x] Docker dev-tools сервис (profile: dev)

## Дерево проекта

```
/home/g/gsm/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/         (config, database, security, dependencies, minio_client, celery_app)
│   │   ├── models/       (models.py — 9 ORM)
│   │   ├── schemas/      (schemas.py, catalog_schemas.py, etl_schemas.py, search_schemas.py, sales_schemas.py)
│   │   ├── routers/      (auth, catalog, imports, search, sales_copilot)
│   │   ├── services/     (crud, excel_parser, normalizer, etl_pipeline, vector_indexer, search_engine, sales_indexer, sales_copilot)
│   │   └── tasks/        (etl_tasks)
│   ├── docker/           (init.sql, migration_fix.sql, Dockerfile)
│   └── docker-compose.yml
├── frontend/
│   ├── app/
│   │   ├── login/
│   │   ├── dashboard/    (page, search, imports, sales-copilot)
│   │   └── layout.tsx
│   ├── components/       (ui/* shadcn, SalesCopilot)
│   ├── lib/              (api.ts, sse-client.ts)
│   └── store/            (auth-store.ts)
├── context/              (10 .md файлов)
├── scripts/              (start-session, update-docs)
└── .opencode/
```

## Следующая задача

1. Установить sentence-transformers для cross-encoder re-ranker (опционально)
2. Развернуть MCP-сервер (опционально, для Claude Desktop)
3. Страница /dashboard/clients
4. Unit-тесты для ETL, поиска и Sales Copilot
5. Этап 8: Billing + predictive analytics
