# HISTORY.md — Хроника проекта GSM

## 2026-06-23 — Sales Copilot 2.0 (RAG-indicator + hybrid search)

**Контекст:** Интеграция Sales Copilot 2.0 в GSM: SSE-стриминг с RAG-indicator, гибридный поиск (Vector + FTS + RRF), 120 seed-кейсов, Docker-развёртывание фронтенда.

**Ключевые решения:**
1. Единая Qdrant collection `sales_objections` с named vectors "default" + "response"
2. Три отдельных LLM-вызова (последовательно) вместо одного на 3 варианта — чище SSE
3. AsyncQdrantClient v2: `.query_points()` вместо `.search()`
4. `API_URL` (без `NEXT_PUBLIC_`) для server-side Next.js rewrites
5. FTS-фильтры динамические (if param) — обход бага asyncpg с NULL
6. 20 новых seed-кейсов (storage + harmful) — enum values добавлены

**Создано:**
- `backend/app/services/sales_copilot.py`, `hybrid_search.py`, `embedding.py`, `qdrant_client.py`
- `backend/app/routers/sales_copilot.py`, `backend/app/schemas/sales_schemas.py`
- `frontend/components/SalesCopilotChat.tsx` (874 строки)
- `sales-copilot/dashboard.md`, `sd-sales-copilot-logic.md`, `sales-copilot-full-plan.md`, `SALES_COPILOT_SUMMARY.md`
- `sales-copilot/seed_storage_harmful_cases.sql`
- Docker-контейнер `oil-frontend`, обновлён `nginx.conf`
- 120 seed-кейсов в PostgreSQL + Qdrant (было 100 → 120)

## 2026-06-17 — Основание проекта

**Контекст:** Создаётся B2B SaaS-платформа для подбора моторных масел с AI-консультантом.

**Ключевые решения:**
1. **Архитектура:** Modular Monolith (Python FastAPI), а не микросервисы — для скорости разработки MVP
2. **Multi-tenancy:** RLS на PostgreSQL + do_orm_execute в SQLAlchemy — двойная защита
3. **Стек:** 100% Open Source, без проприетарных лицензий, РФ-safe
4. **Разделение данных:** Чёткие маркеры «Заводская рекомендация (OEM)» vs «Допуск»
5. **Биллинг:** Grace Period 3 дня (мягкая блокировка, потом Read-Only)
6. **Модульность:** Webpack Module Federation для плагинов
7. **LLM:** Локальная модель на сервере (Qwen 2.5 / DeepSeek / Saiga), никаких облачных API
8. **ETL:** Трёхуровневая дедупликация (хэш → fuzzy → бизнес-правила)

**Создано:**
- backend/ — скелет FastAPI-приложения с инфраструктурой
- context/ — полный набор документации и правил
- scripts/ — ритуалы начала/конца сессии
- Git-репозиторий с pre-commit и GitHub remote
