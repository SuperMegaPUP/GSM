# CONTEXT.md — Память AI между сессиями

## Мандат начала сессии

При старте новой сессии AI ОБЯЗАН:
1. Выполнить `bash scripts/start-session.sh`
2. Прочитать `context/RULES.md` — узнать стек и правила
3. Прочитать `context/SNAPSHOT.md` — понять текущее состояние
4. Прочитать `context/BACKLOG.md` — определить следующую задачу
5. Проверить `docker compose ps` — все контейнеры Up
6. Доложить пользователю состояние и предложить план

## Мандат конца сессии

Перед завершением сессии AI ОБЯЗАН:
1. Проверить синтаксис всех `.py`: `find backend -name "*.py" -exec python3 -m py_compile {} \;`
2. Выполнить `bash scripts/update-docs.sh`
3. Проверить что `git status` чистый
4. Сделать `git add -A && git commit -m "..." && git push origin main`
5. Доложить что закоммичено

## Критические параметры проекта

| Параметр | Значение |
|---|---|
| Название | GSM (Get Some Motor oil) |
| Репозиторий | GitHub, origin = git@github.com:/GSM |
| Ветка по умолчанию | main |
| Структура | Modular Monolith (Python) |
| База данных | PostgreSQL 16 + pgvector |
| LLM | Локальная, Qwen 2.5 / DeepSeek / Saiga |
| Порт backend | 8000 |
| Порт frontend | 3000 |
| Основной интерфейс | Web UI (Next.js) |
| Доп. каналы | Telegram-бот |

## Критические заметки о состоянии

- Sales Copilot 2.0 запущен: `/dashboard/sales-copilot` (новый SalesCopilotChat) + страница поиска масел (старый SalesCopilot)
- 120 seed-кейсов в Qdrant (9 категорий, включая storage + harmful)
- LLM на `http://192.168.122.1:1234/v1` (Qwen / DeepSeek / Saiga)
- AsyncQdrantClient v2: без `.search()`, используем `.query_points()`
- FTS в hybrid_search требует `await db.rollback()` при ошибке
- Frontend — Docker-контейнер `oil-frontend:3000`, Nginx upstream
- `API_URL` для server-side rewrites (не `NEXT_PUBLIC_`)

## Запреты
- НЕ использовать проприетарные/заблокированные в РФ сервисы
- НЕ хардкодить пароли, токены, секреты
- НЕ писать `# TODO`, `pass`, `raise NotImplementedError`
- НЕ отклоняться от архитектуры без подтверждения пользователя
