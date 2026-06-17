# RULES.md — Конституция проекта GSM

## 1. Технологический стек (строго)

| Компонент | Технология | Версия |
|---|---|---|
| Backend | Python (FastAPI) | 3.12 / 0.115+ |
| ORM | SQLAlchemy | 2.0+ (async) |
| Валидация | Pydantic | V2 |
| DB | PostgreSQL + pgvector | 16 |
| Vector DB | Qdrant | latest |
| Кэш / Брокер | Redis | 7 |
| S3 | MinIO | latest |
| Очереди | Celery + Redis | 5.4+ |
| Frontend | Next.js (App Router) | 14+ |
| UI Kit | shadcn/ui + TailwindCSS | latest |
| LLM | Qwen 2.5 / DeepSeek / Saiga | любая |

## 2. Архитектурные принципы

- **Modular Monolith** — всё в одном репозитории, разделение по `app/domains/...`
- **Multi-tenancy** — изоляция данных через RLS (PostgreSQL) + `do_orm_execute` (SQLAlchemy)
- **Атомарность** — каждый микросервис/модуль = отдельная папка со своей моделью, схемой, роутером, сервисом
- **Graceful Degradation** — если LLM/векторная БД упала, переключаться на fallback-режим (SQL-поиск)

## 3. Правила кодирования

### 3.1 Python
- Строгая типизация: `TypeHints` везде, никаких `Any` без необходимости
- Все Pydantic модели — V2 стиль (`ConfigDict(from_attributes=True)`)
- Все SQLAlchemy модели — `Mapped` / `mapped_column`, async-сессии
- Комментарии — на русском, краткие, только там где логика неочевидна
- Обработка ошибок: `try/except` с конкретным типом исключения, возврат корректного HTTP-статуса
- Никаких `# TODO`, `pass`, `raise NotImplementedError` — только рабочий код

### 3.2 API
- Префикс: `/api/v1/...`
- Все эндпоинты возвращают Pydantic модели (не сырые dict)
- SSE для стриминга LLM-ответов
- JWT в Bearer-заголовке для аутентификации

### 3.3 База данных
- Миграции через Alembic (но стартовый `init.sql` для Docker)
- Все таблицы с tenant-aware сущностями имеют `company_id UUID NOT NULL`
- Индексы на `company_id`, внешние ключи, поисковые поля

## 4. Security (SECURITY.md)
- Пароли хранятся только bcrypt
- JWT-токены с expire (по умолчанию 24ч)
- Все секреты — в переменных окружения, никогда в коде
- RLS включена на всех бизнес-таблицах
- Non-root пользователь в Docker-контейнерах
- GitHub-токены и пароли НИКОГДА не пишутся в открытом виде в чат или код

## 5. Quality Gates (перед коммитом)
1. `ruff check .` — стиль кода
2. `pytest` — юнит-тесты (покрытие > 80%)
3. `python3 -m py_compile` всех `.py` — синтаксис
4. `docker compose build --no-cache backend` — сборка проходит
