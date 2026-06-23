# GSM Sales Copilot — RAG + MCP Integration Guide

> **Архитектура:** LLM + MCP-адаптер + Qdrant (семантический поиск) + PostgreSQL (CRUD/RLHF) + FastAPI (orchestration)
>
> **Что решает:** LLM даёт поверхностные ответы, потому что не знает специфики работы с возражениями по моторным маслам. RAG-пайплайн подаёт LLM 3-5 релевантных кейсов из базы знаний до генерации ответа. MCP-адаптер даёт LLM инструменты для самостоятельного поиска и логирования обратной связи.

---

## 📦 Что в коробке

```
sales-copilot-rag/
├── objection_cases.json          ← 100 кейсов, распарсенных из вашего файла
├── objection_cases.sql           ← SQL INSERT для заливки в PostgreSQL
├── migration_objection_cases.sql ← Схема таблицы + индексы + RLS
├── seed_objection_cases.py       ← Создаёт Qdrant collection + индексирует 100 кейсов
├── mcp-objection-server.ts       ← MCP-сервер (4 инструмента для LLM)
├── sales_copilot_service.py      ← FastAPI router с эндпоинтами
├── INTEGRATION.md                ← Этот файл
└── stats.md                      ← Статистика по кейсам
```

---

## 🏗️ Архитектура

```
                          Менеджер (Sales Copilot UI)
                                    │
                                    ▼
                      POST /api/v1/sales/handle-objection
                                    │
                          ┌─────────┴─────────┐
                          │                   │
                          ▼                   ▼
                  ┌─────────────┐     ┌──────────────┐
                  │ Qdrant      │     │ FastAPI      │
                  │ sales_      │     │ sales_       │
                  │ objections  │     │ copilot      │
                  │ (vector)    │     │ service      │
                  └──────┬──────┘     └──────┬───────┘
                         │                   │
                         │   ┌───────────────┘
                         │   │
                         ▼   ▼
                   ┌────────────────┐
                   │ LLM Server     │
                   │ (Qwen / DS)    │
                   │                │
                   │  MCP client ───┼──→ MCP Server (mcp-objection-server.ts)
                   │                │         │
                   │  tools:        │         ▼
                   │  • search      │     HTTP → FastAPI
                   │  • get_by_id   │     (4 endpoints)
                   │  • list_cats   │
                   │  • feedback    │
                   └────────────────┘
                                    │
                                    ▼
                          ┌──────────────────┐
                          │ PostgreSQL       │
                          │ objection_cases  │
                          │ sales_interactions│
                          └──────────────────┘
```

---

## 🚀 Шаги интеграции (для локальной модели-кодера)

### Шаг 1. Применить миграцию

```bash
# Из корня проекта
psql -d gsm -f download/sales-copilot-rag/migration_objection_cases.sql
```

Проверить:
```sql
\d objection_cases
-- Должна быть таблица с колонками:
-- id, tenant_id, number, category, category_label,
-- objection_text, response_text, tags, content_hash,
-- is_seed, is_published, quality_score, usage_count, qdrant_point_id
```

### Шаг 2. Залить 100 кейсов

```bash
psql -d gsm -f download/sales-copilot-rag/objection_cases.sql
```

Проверить:
```sql
SELECT category, COUNT(*) FROM objection_cases GROUP BY category;
-- price: 20, quality: 20, logistics: 15, service: 15,
-- brand: 10, business: 10, closing: 10
```

### Шаг 3. Создать Qdrant collection + индексировать кейсы

```bash
pip install sentence-transformers psycopg2-binary requests

export DATABASE_URL="postgresql://gsm:gsm@localhost:5432/gsm"
export QDRANT_URL="http://localhost:6333"

python download/sales-copilot-rag/seed_objection_cases.py
```

**Что произойдёт:**
1. Загрузится модель `paraphrase-multilingual-MiniLM-L12-v2` (90 МБ, мультиязычная)
2. Удалится старая Qdrant collection `sales_objections` (если была)
3. Создастся новая с payload-индексами для фильтрации
4. Все 100 кейсов векторизуются (batch по 16) — ~30 сек на CPU
5. Зальются в Qdrant
6. `qdrant_point_id` запишется обратно в PostgreSQL
7. Запустится verification-тест с 5 тестовыми запросами

**Проверка:**
```bash
curl http://localhost:6333/collections/sales_objections
# Должно вернуть: {"result": {"points_count": 100, ...}}
```

### Шаг 4. Добавить FastAPI router

В `backend/app/main.py`:
```python
from app.routers import sales_copilot

app.include_router(sales_copilot.router)
```

Скопировать файл `sales_copilot_service.py` в `backend/app/routers/sales_copilot.py`.

Убедиться, что есть зависимость `app.services.embedding.embed_text`:
```python
# backend/app/services/embedding.py
from sentence_transformers import SentenceTransformer
from functools import lru_cache

@lru_cache
def _model():
    return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

async def embed_text(text: str) -> list[float]:
    return _model().encode([text])[0].tolist()

async def embed_batch(texts: list[str]) -> list[list[float]]:
    return _model().encode(texts, batch_size=16).tolist()
```

И `app.services.qdrant_client.get_qdrant`:
```python
# backend/app/services/qdrant_client.py
from qdrant_client import AsyncQdrantClient
from app.core.config import settings

_client = None

async def get_qdrant() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.QDRANT_URL)
    return _client
```

### Шаг 5. Запустить MCP-сервер

```bash
npm install @modelcontextprotocol/sdk
export GSM_API_URL="http://localhost:8000/api/v1"
export GSM_API_TOKEN="<JWT токен технолога>"
export GSM_TENANT_ID="<UUID компании>"

npx tsx download/sales-copilot-rag/mcp-objection-server.ts
```

**Регистрация в Claude Desktop / Cursor:**
```json
{
  "mcpServers": {
    "gsm-sales-copilot": {
      "command": "tsx",
      "args": ["./download/sales-copilot-rag/mcp-objection-server.ts"],
      "env": {
        "GSM_API_URL": "http://localhost:8000/api/v1",
        "GSM_API_TOKEN": "<JWT>",
        "GSM_TENANT_ID": "<UUID>"
      }
    }
  }
}
```

### Шаг 6. Тест end-to-end

```bash
# 1. Поиск через MCP-сервер (имитируем вызов LLM)
curl -X POST http://localhost:8000/api/v1/sales/search-objection-cases \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"q": "У вас слишком дорого", "limit": 3}'

# 2. Главный эндпоинт — Sales Copilot с RAG
curl -X POST http://localhost:8000/api/v1/sales/handle-objection \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "objection": "А почему у вас масло так дорого? На Авито в два раза дешевле",
    "category": "price",
    "client_info": {"company": "ООО Логистик", "car_brand": "Toyota"}
  }'
```

---

## 🧠 4 MCP-инструмента для LLM

### 1. `search_objection_cases` — ГЛАВНЫЙ инструмент

**Когда LLM вызывает:** при любом возражении клиента (по цене, качеству, срокам и т.д.)

**Что делает:**
1. Векторизует возражение клиента
2. Ищет топ-K похожих кейсов в Qdrant (косинусное сходство)
3. Фильтрует по категории/бренду/типу масла (если указано)
4. Fallback на PostgreSQL FTS если Qdrant недоступен
5. Инкрементит `usage_count` для найденных кейсов

**Параметры:**
| Имя | Тип | Описание |
|---|---|---|
| `objection` | string (required) | Текст возражения |
| `category` | enum (optional) | price/quality/logistics/service/brand/business/closing |
| `car_brand` | string (optional) | Toyota, Honda, etc. |
| `fluid_type` | string (optional) | engine, atf, cvt, gear, hydraulic |
| `limit` | int (default 5) | 1-10 |
| `min_score` | float (default 0.6) | 0.0-1.0 |

### 2. `get_case_by_id` — Точечный lookup

**Когда LLM вызывает:** когда нужно процитировать конкретный кейс или когда ID уже известен из предыдущего поиска.

### 3. `list_categories` — Обзор категорий

**Когда LLM вызывает:** в начале диалога, когда непонятно, к какой категории отнести возражение.

### 4. `log_response_feedback` — RLHF

**Когда LLM вызывает:** после того, как менеджер использовал её ответ. Положительная обратная связь повышает `quality_score` кейса на +0.05, отрицательная понижает на -0.10. Если качество падает ниже 0.3 — кейс автоматически скрывается (is_published=false) и попадает в очередь ревью технолога.

---

## 📊 Системный промпт для LLM

Сам промпт строится динамически в `_build_system_prompt()` и содержит:

```
Ты — Sales Copilot в системе GSM...
Твоя задача: дать менеджеру 3 варианта ответа на возражение клиента.

ВАЖНО:
1. Каждый ответ должен быть конкретным, с реальными цифрами/спецификациями
2. Не копируй кейсы дословно — адаптируй под контекст клиента
3. Все три ответа должны быть РАЗНЫМИ по тональности:
   - 1. Рациональный — цифры, факты, расчёт окупаемости
   - 2. Эмпатичный — понимание, мягкая альтернатива
   - 3. Перехват инициативы — закрытие на следующее действие

## 📚 Релевантные кейсы из базы знаний GSM

### Кейс 1 (категория: Ценовые возражения)
**Возражение:** У вас слишком дорого
**Проверенный ответ:** Я понимаю ваше желание сэкономить. Давайте посмотрим не на цену за канистру...

### Кейс 2 (категория: Ценовые возражения)
**Возражение:** ...

## 👤 Контекст клиента
{"company": "ООО Логистик", "car_brand": "Toyota"}

## 💬 Предыдущий диалог
<сообщения из чата>

---
Сгенерируй 3 варианта ответа на возражение ниже.
```

---

## 🔄 Жизненный цикл кейса

```
                ┌────────────────────┐
                │ Технолог добавляет │
                │ новый кейс через   │
                │ веб-интерфейс      │
                └─────────┬──────────┘
                          │
                          ▼
                ┌────────────────────┐
                │ POST /objection-   │
                │ cases              │
                │ (create_case)      │
                └─────────┬──────────┘
                          │
                ┌─────────┴──────────┐
                │                    │
                ▼                    ▼
        ┌──────────────┐    ┌──────────────┐
        │ PostgreSQL   │    │ Qdrant       │
        │ insert row   │    │ upsert point │
        │ + embedding  │    │ + payload    │
        └──────────────┘    └──────────────┘
                          │
                          ▼
        ┌────────────────────────────────┐
        │ LLM использует кейс в RAG      │
        │ (search_objection_cases)       │
        └─────────────┬──────────────────┘
                      │
                      ▼
        ┌────────────────────────────────┐
        │ Менеджер отмечает: помогло/нет │
        │ (log_response_feedback)        │
        └─────────────┬──────────────────┘
                      │
            ┌─────────┴─────────┐
            │                   │
            ▼                   ▼
    quality_score ↑      quality_score ↓
    usage_count ↑        если < 0.3 →
    кейс чаще            is_published = false
    предлагается         (скрыт, ждёт ревью)
```

---

## 📈 Метрики и аналитика

В таблице `sales_interactions` логируется каждый вызов Sales Copilot:

```sql
SELECT
    date_trunc('day', created_at) AS day,
    COUNT(*) AS interactions,
    COUNT(DISTINCT user_id) AS active_managers,
    AVG(array_length(retrieved_case_ids, 1)) AS avg_cases_used
FROM sales_interactions
WHERE tenant_id = $1
GROUP BY day
ORDER BY day DESC;
```

```sql
-- Топ кейсов по использованию (для аналитики технолога)
SELECT id, category_label, objection_text,
       usage_count, quality_score,
       last_used_at
FROM objection_cases
WHERE is_published = true
ORDER BY usage_count DESC
LIMIT 20;
```

```sql
-- Кейсы под ревью (quality_score упал)
SELECT id, objection_text, quality_score, usage_count
FROM objection_cases
WHERE quality_score < 0.4 AND is_published = false
ORDER BY quality_score ASC;
```

---

## ⚠️ Известные ограничения и roadmap

### Что уже работает:
- ✅ 100 кейсов в 7 категориях
- ✅ Векторный поиск (Qdrant) + FTS fallback (PostgreSQL)
- ✅ Multi-tenant изоляция (RLS + payload filtering)
- ✅ RLHF через feedback endpoint
- ✅ MCP-адаптер для LLM с 4 инструментами
- ✅ Логирование всех взаимодействий

### Что нужно добавить (post-MVP):
- 🔲 **Embeddings в response_text** — сейчас индексируется только objection. Можно добавить второй вектор для поиска «похожих ответов».
- 🔲 **Cross-encoder re-ranking** — после Qdrant top-20, прогнать через `bge-reranker-base` для точного ранжирования.
- 🔲 **Hybrid search** — combine vector (Qdrant) + FTS (PostgreSQL) scores с весами.
- 🔲 **Auto-suggest cases** — при вводе менеджером возражения в UI, показывать топ-3 кейса в реальном времени (debounce 300ms).
- 🔲 **Case deduplication** — при создании нового кейса проверять, нет ли уже похожего (cosine > 0.9).
- 🔲 **A/B testing prompts** — разные системные промпты для разных групп менеджеров.
- 🔲 **Voice-to-objection** — Yandex SpeechKit / Whisper → автоматический вызов Sales Copilot.
- 🔲 **Predictive case suggestion** — если менеджер открыл карточку клиента Toyota, предзагрузить кейсы с `car_brand=Toyota`.

---

## 🎯 Ожидаемый эффект

**До RAG:**
> «Понимаю, что цена важна. Но наше масло качественное и прослужит долго. У нас бывают скидки, обратитесь к менеджеру.»

**После RAG (с кейсом obj_001):**
> «Понимаю ваше желание сэкономить. Давайте посмотрим не на цену за канистру, а на совокупную стоимость владения. Наше масло Gazpromneft Super 5W-30 содержит пакет присадок ZDDP, который снижает трение и экономит до 5% топлива, а также позволяет увеличить интервал замены с 7 500 до 15 000 км. Для вашего Toyota Hilux Surf 2003 (1KZ-TE) экономия на топливе и фильтрах за 30 000 км пробега перекроет разницу в цене канистры.»

Разница — **конкретика вместо общих слов**. Это и есть ценность RAG для Sales Copilot.
