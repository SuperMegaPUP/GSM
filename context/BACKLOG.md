# BACKLOG.md — Бэклог проекта GSM

## Статус: MVP полностью готов — Все 7 этапов выполнены ✅

---

**Условные обозначения:**
- [x] — выполнено
- [ ] — в работе / ожидает
- [~] — частично

---

## Этап 1: Инфраструктура и База данных ✅

- [x] 1.1: `docker-compose.yml` (7 сервисов: postgres+pgvector, qdrant, redis, minio, backend, celery-worker, nginx)
- [x] 1.2: `docker/init.sql` (9 таблиц, ENUMs, RLS, индексы, триггеры, seed)
- [x] 1.3: `app/core/config.py` (Pydantic Settings)
- [x] 1.4: `app/core/database.py` (SQLAlchemy async + RLS через do_orm_execute)
- [x] 1.5: `app/main.py` (FastAPI app + healthcheck)
- [x] 1.6: `context/` — 10 .md файлов
- [x] 1.7: `scripts/start-session.sh` и `update-docs.sh`
- [x] 1.8: `.gitignore`, `.pre-commit-config.yaml`
- [x] 1.9: Git init + GitHub + первый коммит

---

## Этап 2: SQLAlchemy модели и Pydantic схемы ✅

- [x] 2.1: Модели ORM — `app/models/models.py` (9 моделей + 5 ENUMs)
- [x] 2.2: Pydantic схемы — auth, catalog, ETL, search, sales
- [x] 2.3: Alembic — (заменено на init.sql + migration_fix.sql)

---

## Этап 3: Backend API ✅

- [x] 3.1: Auth — регистрация/логин, JWT, зависимость get_current_user
- [x] 3.2: Мультитенантность — RLS + do_orm_execute + dependencies.get_current_active_user
- [x] 3.3: CRUD справочников (бренды, модели, варианты, жидкости)
- [x] 3.4: MinIO клиент + Celery app
- [x] 3.5: Imports API (upload, status, list history)

---

## Этап 4: ETL-пайплайн ✅

- [x] 4.1: Парсер Excel (pandas + openpyxl, двухуровневые заголовки)
- [x] 4.2: Нормализатор (FluidNormalizer, хэши, года)
- [x] 4.3: Дедупликация (composite UNIQUE + ON CONFLICT)
- [x] 4.4: Асинхронные задачи Celery (parse_excel_task, index_qdrant_task)
- [x] Импорт: 11,141 строк из katalog_gsm.xlsx

---

## Этап 5: LLM + RAG ✅

- [x] 5.1: Векторизация справочников в Qdrant (sentence-transformers)
- [x] 5.2: Гибридный поиск (SQL + Qdrant fallback) + модель-селектор
- [x] 5.3: Эндпоинт рекомендаций с OEM/analogue маркерами

---

## Этап 6: Sales Copilot ✅

- [x] 6.1: Sales Copilot 2.0 — SSE-стриминг, RAG-indicator, hybrid search (Vector + FTS + RRF)
- [x] 6.2: 100 seed-кейсов (7 категорий) в PostgreSQL + Qdrant (named vectors "default" + "response")
- [x] 6.3: Роутер /api/v1/sales/* + таблица sales_interactions
- [x] 6.4: Frontend SalesCopilotChat.tsx (SSE, 3 варианта, копирование, фидбек)
- [x] 6.5: Docker-контейнер oil-frontend + Nginx upstream
- [x] 6.6: +20 seed-кейсов storage + harmful (120 total)

---

## Этап 7: Frontend ✅

- [x] 7.1: Next.js 14 + shadcn/ui v4 + Zustand + App Shell
- [x] 7.2: Страница подбора масел (поиск + карточки + модель-селектор)
- [x] 7.3: Sales Copilot (SSE-стриминг, 3 стиля)
- [x] 7.4: Imports (Drag&Drop, прогресс, история)

---

## Этап 8: Бизнес-логика

- [ ] 8.1: Биллинг (Grace Period, State Machine)
- [x] 8.2: Предиктивная аналитика (7 правил, nightly trends, API, дашборд)
- [ ] 8.3: Telegram-bot (webhooks, быстрые команды)

---

## Этап 9: CI/CD + Деплой

- [ ] 9.1: CI пайплайн (lint → test → build → deploy)
- [ ] 9.2: Staging + Prod стенды
- [ ] 9.3: Мониторинг (VictoriaMetrics + Grafana)

---

## Будущие модули

- [ ] Модуль «Квиз»
- [ ] Интеграция с CRM (Bitrix24, AmoCRM webhooks)
- [ ] Телефония (Yandex SpeechKit / Whisper)
- [ ] Страница /dashboard/clients
