
---

## Сессия 7 — 2026-07-02 — UI Redesign + PVL импорт

**Стек:** Next.js 14 / FastAPI / SQLAlchemy async / Qdrant / PostgreSQL

**Что сделано:**

- VehicleTypeTabs — 5 вкладок (легковые/грузовые/спецтехника/мото/бензопилы) с иконками, счётчиками, анимацией индикатора
- FluidCard редизайн — ранг-бейдж (★ Основное/Alt/Сноска), левая граница по rank (зелёный/синий/серый), чипсы условий
- SidePanel — сводка (бренды/модели/рекомендации), архитектура узлов, CTA импорта
- nodeTypes — SUSPENSION + группы hydraulic/other
- Двухколоночная сетка search page (main + sidebar, sticky)
- Динамические поля формы (Код кузова для легковых и т.д.)
- Неактивные вкладки отключены (грузовые/спецтехника/мото — нет данных)
- Исправлен SSE-клиент: переписан под протокол variant_start/variant_chunk/variant_done
- Исправлена ошибка Cannot read properties of undefined (reading 'length') в SalesCopilot

**Решения:**
- Все вкладки кроме Легковые отключены — в БД только passenger_car данные
- Счётчики: 2 920 вариантов, 36 брендов (реальные цифры из oil_saas)
- CSS-классы переименованы в node-pill--{group} для единообразия

**Следующий шаг:**
- Код кузова (body_code) — новый параметр поиска, нужна поддержка на бэкенде


---

## Сессия 6 — 2026-07-01 — PVL импорт (36 брендов, ~20k рекомендаций)

**Стек:** FastAPI / SQLAlchemy async / Qdrant / Excel (pandas)

**Что сделано:**

- Миграция БД: SUSPENSION в node_type/fluid_type enum, 6 новых колонок, UNIQUE INDEX заменён
- Создан pvl_parser.py — 2929 авто, 36 брендов, 20149 рекомендаций
- ETL расширен: process_pvl_batch с variant hash, auto-detect PVL в parse_excel_task
- Qdrant payload: recommendation_rank, applicability_conditions, fluid_name_override
- PVL импортирован: 20084 рекомендаций, 36 брендов, 2925 моделей, 5156 вариантов
- Frontend: FluidCardWrapper с RankBadge, сортировка по rank, API возвращает recommendation_rank
- Frontend пересобран и запущен на порту 3000
- Исправление CAST(:cond AS jsonb) — asyncpg + named params

**Решения:**
- PVL данные в тенанте pvl@test.ru (отдельно от JDM test@test.ru)
- recommendation_rank 1-3 = основное/альт1/альт2, 4+ = сноска

**Следующий шаг:**
- Залить PVL в test@test.ru или дать инструкцию
- Продлить canonical_name в fluids (ALTER TABLE hang)

---

## Сессия 5 — 2026-07-02 — Predictive Analytics + Баги фидбека и статистики

**Стек:** FastAPI 0.115+ / SQLAlchemy 2.0 async / Pydantic V2 / Next.js 14 / Celery Beat

**Что сделано:**

- Созданы 7 правил предиктивной аналитики в `predictive_analytics.py` (troubled cases, golden cases, popular objections, empty categories, и др.)
- Создана таблица `daily_trends` + модель `DailyTrend` + миграция `migration_daily_trends.sql`
- Создана Celery задача `compute_trends_task` с 3 метриками (objections_total, objections_by_category, case_stats)
- Добавлен `compute-trends-daily` в `celery_app.conf.beat_schedule`
- Созданы API endpoints: `GET /analytics/trends?days=30` (live today + historical), `GET /analytics/insights`, `GET /analytics/cases/{id}/history`
- Создана страница `/dashboard/analytics` с KPI карточками, трендами, планом действий и инсайтами
- Добавлена ссылка «Аналитика» в боковое меню
- Фикс бэкенда: добавлен импорт timedelta в `analytics.py`
- **Баг fix:** `record_objection_feedback` в `sales_copilot.py` — `:outcome::objection_outcome → CAST(:outcome AS objection_outcome)` — feedback endpoint был сломан
- **Баг fix:** Route ordering — `/objection-cases/stats` теперь перед `{case_id}` — stats endpoint был недоступен
- **Фича:** Live-счётчик возражений сегодня в `GET /analytics/trends` (не из nightly джобы, а прямой подсчёт)
- **Фича:** Защита от двойного нажатия кнопок фидбека в Sales Copilot (`submittedRef`, `disabled`)
- **Фича:** Подсветка кнопок: зелёная (Сработало) / красная (Не сработало) + toast через sonner
- **Фича:** Подгрузка деталей кейса в панель «Кейс в фокусе» (GET /sales/objection-cases/{id})
- **Фича:** Живая статистика сессии в Sales Copilot (total, total_used, total_won/lost, avg_success_rate)
- **Фича:** Добавлен `total_lost` в `StatsResponse` + SQL
- Инфра: celery-beat healthcheck отключён (был curl localhost:8000 в контейнере без веб-сервера)
- Инфра: celery-beat добавлен volume mount для live-кода

**Решения:**
- Тренды хранятся в `daily_trends` (JSONB) для быстрых графиков, а сегодняшняя дата считается live
- Финал фидбека — только первый case_id в variant (один клик = +1 usage_count)
- Route order: статический `/stats` перед динамическим `/{case_id}`

**Следующий шаг:**
- sentence-transformers для cross-encoder re-ranker
- MCP-сервер (опционально)
- Страница /dashboard/clients
- Unit-тесты

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
