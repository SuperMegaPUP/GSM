# BACKLOG.md — Бэклог проекта GSM

## Статус: Этап 1 (Инфраструктура) — ВЫПОЛНЕН

---

**Условные обозначения:**
- [x] — выполнено
- [ ] — в работе / ожидает
- [~] — частично

---

## Этап 1: Инфраструктура и База данных (1 неделя) ✅

- [x] 1.1: `docker-compose.yml` (postgres+pgvector, qdrant, redis, minio, backend, nginx)
- [x] 1.2: `docker/init.sql` (9 таблиц, ENUMs, RLS, индексы, триггеры, seed)
- [x] 1.3: `app/core/config.py` (Pydantic Settings)
- [x] 1.4: `app/core/database.py` (SQLAlchemy async + RLS через do_orm_execute)
- [x] 1.5: `app/main.py` (FastAPI app + healthcheck)
- [x] 1.6: `context/` — RULES, ARCHITECTURE, BACKLOG, SNAPSHOT, WORKLOG, HISTORY, VERSIONING, CONTEXT, RITUALS, TEMPLATES
- [x] 1.7: `scripts/start-session.sh` и `update-docs.sh`
- [x] 1.8: `.gitignore`, `.pre-commit-config.yaml`
- [x] 1.9: Git init + GitHub + первый коммит

---

## Этап 2: SQLAlchemy модели и Pydantic схемы (3 дня)

- [ ] 2.1: Модели ORM — `app/models/__init__.py`, `app/models/company.py`, `app/models/user.py`, `app/models/car.py`, `app/models/fluid.py`, `app/models/recommendation.py`
- [ ] 2.2: Pydantic схемы — `app/schemas/auth.py`, `app/schemas/catalog.py`, `app/schemas/etl.py`
- [ ] 2.3: Alembic — инициализация, первая миграция (sync с init.sql)

**Промпт для LLM (скопировать):**
```
Задача 2: ORM Модели и Pydantic схемы.
Основываясь на init.sql, напиши следующие файлы:
1. app/models/ — SQLAlchemy 2.0 модели (Mapped, mapped_column).
   - Fluid: oem_approvals (JSONB), viscosity_sae, api_class, fluid_type (Enum)
   - Recommendation: volume_liters, volume_with_filter, is_oem_recommendation
2. app/schemas/ — Pydantic V2 схемы для API (CarSearchRequest, FluidResponse, RecommendationResponse).
3. app/schemas/etl_schemas.py — схемы для нормализации Excel (RawExcelRow, NormalizedFluid).
```

---

## Этап 3: Backend API (4 дня)

- [ ] 3.1: Auth — регистрация/логин, JWT, зависимость get_current_user
- [ ] 3.2: Мультитенантность — middleware / зависимость get_tenant_db_session
- [ ] 3.3: CRUD справочников (бренды, модели, варианты, жидкости)

---

## Этап 4: ETL-пайплайн (5 дней)

- [ ] 4.1: Парсер Excel (pandas + openpyxl, двухуровневые заголовки, merged cells)
- [ ] 4.2: LLM-нормализатор (очистка названий масел через локальную модель)
- [ ] 4.3: Дедупликация (хэш + fuzzy + бизнес-правила)
- [ ] 4.4: Интерфейс технолога (Review Grid, Diff, Approve/Reject)

---

## Этап 5: LLM + RAG (5 дней)

- [ ] 5.1: Индексация справочников в Qdrant
- [ ] 5.2: Гибридный поиск (SQL + Vector) + Re-ranking
- [ ] 5.3: Эндпоинт рекомендаций с маркерами OEM/Допуск

---

## Этап 6: Sales Copilot (3 дня)

- [ ] 6.1: Векторизация базы возражений
- [ ] 6.2: RAG-поиск + генерация 3 вариантов ответов
- [ ] 6.3: UI-виджет (плавающая панель, копирование в буфер)

---

## Этап 7: Frontend (5 дней)

- [ ] 7.1: Next.js + shadcn/ui + Layout
- [ ] 7.2: Страница подбора масел (поиск + карточки)
- [ ] 7.3: Чат с AI (SSE-стриминг)
- [ ] 7.4: Дашборд предиктивной аналитики

---

## Этап 8: Бизнес-логика (4 дня)

- [ ] 8.1: Биллинг (Grace Period, State Machine)
- [ ] 8.2: Предиктивная аналитика (Celery Beat, ночные джобы)
- [ ] 8.3: Telegram-bot (webhooks, быстрые команды)

---

## Этап 9: CI/CD + Деплой (3 дня)

- [ ] 9.1: GitLab CI пайплайн (lint → test → build → deploy)
- [ ] 9.2: Staging + Prod стенды
- [ ] 9.3: Мониторинг (VictoriaMetrics + Grafana)

---

## Будущие модули

- [ ] Модуль «Квиз» (Webpack Module Federation)
- [ ] Интеграция с CRM (Bitrix24, AmoCRM webhooks)
- [ ] Телефония (Yandex SpeechKit / Whisper)
