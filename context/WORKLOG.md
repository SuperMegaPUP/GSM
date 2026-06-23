
---

## Сессия от 2026-06-23_20-10

**Что сделано:**

- *(автоматическая запись — требуется уточнение)*

**Решения:**
-

**Следующий шаг:**
-


---

## Сессия 3 — 2026-06-23 — Sales Copilot 2.0 + Seed-кейсы

**Стек:** FastAPI 0.115+ / SQLAlchemy 2.0 async / Pydantic V2 / Next.js 14 / Qdrant

**Что сделано:**

- Создана и развёрнута Sales Copilot 2.0: `sales_copilot.py` (SSE-стриминг, 3 варианта последовательно), `hybrid_search.py` (Vector + FTS + RRF + cross-encoder), `embedding.py`, `qdrant_client.py`
- Созданы роутер `/api/v1/sales/*` и таблица `sales_interactions`
- Написан seed-скрипт SQL + создана Qdrant collection `sales_objections` с named vectors "default" + "response"
- Залиты 100 seed-кейсов (7 категорий) в PostgreSQL и Qdrant
- Создан фронтенд `SalesCopilotChat.tsx` (874 строки, SSE, 3 варианта, копирование, фидбек)
- Развёрнут Docker-контейнер `oil-frontend` на сети `backend_default`
- Обновлён Nginx: upstream `frontend` + `location /` прокси
- Исправлены баги: `API_URL` vs `NEXT_PUBLIC_API_URL`, token key (`token` → `access_token`), `min_length=3` → `1`, 422 на `objection_text` → `objection`
- FTS-фикс: динамические фильтры вместо `OR :param::cast`, добавлен `await db.rollback()` при ошибке FTS
- AsyncQdrantClient v2: переход с `.search()` на `.query_points()`
- Добавлены 20 новых seed-кейсов: 10 storage + 10 harmful (enum + INSERT + Qdrant reseed)

**Решения:**
- Единая Qdrant collection `sales_objections` вместо per-tenant
- Named vectors "default" + "response" вместо одного unnamed
- Три отдельных LLM-вызова вместо одного на 3 варианта
- API_URL (без `NEXT_PUBLIC_`) для server-side rewrites

**Следующий шаг:**
- 20 новых seed-кейсов добавлены ✅
- Проверить старый SalesCopilot на странице поиска масел
- Установить sentence-transformers для cross-encoder (опционально)
- Развернуть MCP-сервер (опционально)
- Этап 8: Биллинг + предиктивная аналитика

---

## Сессия от 2026-06-19_08-54

**Что сделано:**

- Исправлено дублирование названий в комбобоксах (убран ComboboxValue)
- Добавлен поиск моделей с debounce (handleModelSearch)
- Добавлена кнопка «Сбросить» для очистки фильтров
- Добавлен фильтр по объёму двигателя (engine_volumes на бэкенде + чипы на фронте)
- Пофикшен ETL: :nt::node_type → CAST(:nt AS node_type) — SQLAlchemy не парсил параметр
- Добавлены счётчики new_rows/duplicates в ETL pipeline
- Пофикшен UnboundLocalError в search_engine.py (rec_stmt вне цикла по вариантам)

**Решения:**
- Фильтр объёма двигателя всегда показывается, даже если один вариант
- При клике на объём — повторный поиск через API с engine_volume

**Следующий шаг:**
- Не определён


---

## Сессия от 2026-06-18_08-51

**Что сделано:**

- *(автоматическая запись — требуется уточнение)*

**Решения:**
-

**Следующий шаг:**
-


---

## Сессия от 2026-06-17_16-03

**Что сделано:**

- *(автоматическая запись — требуется уточнение)*

**Решения:**
-

**Следующий шаг:**
-


---

## Сессия от 2026-06-17_15-42

**Что сделано:**

- *(автоматическая запись — требуется уточнение)*

**Решения:**
-

**Следующий шаг:**
-


---

## Сессия от 2026-06-17_10-25

**Что сделано:**

- *(автоматическая запись — требуется уточнение)*

**Решения:**
-

**Следующий шаг:**
-


---

## Сессия от 2026-06-17_08-49

**Что сделано:**

- *(автоматическая запись — требуется уточнение)*

**Решения:**
-

**Следующий шаг:**
-


---

## Сессия от 2026-06-17_07-50

**Что сделано:**

- *(автоматическая запись — требуется уточнение)*

**Решения:**
-

**Следующий шаг:**
-

# WORKLOG.md — Журнал сессий

## Сессия 1 — 2026-06-17

**Что сделано:**
- Создана архитектура Lean MVP (Modular Monolith, Docker Compose, Python-only)
- Сгенерирован `backend/`: docker-compose, Dockerfile, init.sql, config, database, main, nginx
- Создан `context/`: RULES, ARCHITECTURE, BACKLOG, SNAPSHOT, WORKLOG, HISTORY, VERSIONING, CONTEXT, RITUALS, TEMPLATES
- Созданы `scripts/`: start-session.sh, update-docs.sh
- Настроен git + pre-commit
- Создан GitHub repo GSM, сделан первый коммит и push

**Решения:**
- Отказ от K8s, Temporal, NATS, Go — в пользу Docker Compose + Celery + FastAPI
- Multi-tenancy через RLS + do_orm_execute (двойная изоляция)
- 100% Open Source стек, без проприетарных лицензий

**Следующий шаг:** Этап 2 — SQLAlchemy модели + Pydantic схемы

---

## Сессия 2 — 2026-06-17

**Что сделано:**
- Созданы SQLAlchemy 2.0 async-модели (9 таблиц) с полной типизацией
- Созданы 5 Python-ENUM классов (UserRole, FluidType, NodeType, SubscriptionStatus, ImportStatus)
- Созданы Pydantic V2 схемы для API (Auth, Catalog, ETL)
- Добавлен TenantAwareMixin для единообразной изоляции данных
- ruff + py_compile пройдены, код запушен

**Решения:**
- TimestampMixin остаётся в `database.py` для переиспользования
- TenantAwareMixin добавлен в `models.py` — добавляет `id` + `company_id` всем tenant-таблицам
- Все Fluid-схемы используют `oem_approvals: list` — JSONB массив строк

**Следующий шаг:** Этап 3 — Backend API (Auth, JWT, мультитенантность)
