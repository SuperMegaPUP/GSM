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

## 2026-07-02 — UI Redesign (preview.html) + SSE-фикс

**Контекст:** Приведение фронтенда search page в соответствие с дизайном preview.html: селектор типа техники, переработанные FluidCard с rank-based стилями, боковая панель.

**Ключевые решения:**
1. VehicleTypeTabs — 5 вкладок, только passenger_car активна (нет данных по грузовым/спецтехнике)
2. FluidCard — левая граница и бейдж по recommendation_rank (1=зелёный, 2=синий, 3+=серый)
3. SUSPENSION добавлен в nodeTypes, STEERING → hydraulic, COOLANT → fluids
4. SSE-клиент переписан под реальный протокол variant_start/variant_chunk/variant_done

**Создано/изменено:**
- VehicleTypeTabs.tsx (новый), SidePanel.tsx (новый)
- FluidCard.tsx (редизайн), nodeTypes.tsx (SUSPENSION + группы)
- search/page.tsx (двухколоночная сетка + динамические поля)
- sse-client.ts (fix протокола), globals.css (+90 строк классов)
- tokens.css (--node-hydraulic/other)

## 2026-07-01 — PVL импорт (36 брендов, 20k рекомендаций)

**Контекст:** Загрузка каталога «Каталог подбора PVL.xlsx» (Газпромнефть). 2929 автомобилей, разбивка по узлам с рангами (основное/альт1/альт2/сноски).

**Ключевые решения:**
1. Новый тенант pvl@test.ru — PVL отдельно от JDM, т.к. другой формат данных
2. recommendation_rank 1-3 = основное/альт1/альт2, 4+ = сноска (footnote)
3. Qdrant payload расширен для rank-фильтрации

**Создано:**
- pvl_parser.py — парсинг PVL XLSX (ENGINE/MANUAL/AUTO/DIFF/COOLANT/BRAKE/STEERING/SUSPENSION)
- ETL: process_pvl_batch, auto-detect в parse_excel_task
- Миграция БД: SUSPENSION enum, 6 колонок, UNIQUE INDEX replace

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
