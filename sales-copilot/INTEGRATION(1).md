# Sales Copilot 2.0 — Улучшенный план интеграции

> **Что нового vs Qwen-план:** гибридный поиск (vector + FTS + RRF), cross-encoder re-ranking, named vectors в Qdrant, temporal decay для freshness, structured SSE streaming, RAG-индикатор в UI.

## 📊 Сравнение подходов

| Аспект | Мой план (v1) | План Qwen | **Финальный план (v2)** |
|---|---|---|---|
| Qdrant collection | одна + RLS-фильтр | отдельная на tenant ❌ | **одна + named vectors** ✅ |
| Векторы | один (objection_vector) | один (objection+args) | **два: objection + response** ✅ |
| Поиск | чистый vector | чистый vector | **hybrid: vector + FTS + RRF** ✅ |
| Re-ranking | нет | нет | **bge-reranker-base** ✅ |
| Кэш embeddings | нет | нет | **Redis, TTL 1h** ✅ |
| Freshness | нет | нет | **temporal decay (90d half-life)** ✅ |
| MCP-сервер | production-обязательный | production-обязательный | **опциональный, для технолога** ✅ |
| RLHF | quality_score ±0.05/0.1 | success_count/failure_count | **success/failure + auto-hide <0.3** ✅ |
| Структура ответа | текстовый стрим | текстовый стрим | **structured SSE: rag→variant_start→chunks→done** ✅ |
| UI RAG-индикатор | нет | нет | **показывает кейсы ДО ответа** ✅ |
| Поле arguments | tags[] | arguments[] JSONB | **arguments[] JSONB + tags[]** ✅ |
| customer_segment | нет | есть | **есть (b2b_fleet/b2c_retail/service_station/...)** ✅ |
| outcome | нет | pending/won/lost | **есть + триггер авто-скрытия** ✅ |

## 📦 Что в коробке

```
sales-copilot-ui/
├── preview.html                    ← ИНТЕРАКТИВНОЕ ДЕМО (открыть в браузере!)
├── tokens.css                      ← Design tokens (копия из gsm-design-system)
├── migration_objection_cases_v2.sql ← Обновлённая схема БД
├── hybrid_search.py                ← Hybrid search: vector + FTS + RRF + reranker
├── SalesCopilotChat.tsx            ← React-компонент с RAG-индикатором
└── INTEGRATION.md                  ← Этот файл
```

## 🎨 UI фичи (что увидит менеджер)

1. **RAG-индикатор появляется ПЕРВЫМ** — менеджер видит «найдено 3 кейса» ДО того, как LLM начал отвечать. Это:
   - **Создаёт доверие** («я вижу, на чём основан ответ»)
   - **Даёт контекст** для feedback (какой кейс отметить «не сработал»)
   - **Обучает менеджера** (он читает проверенные кейсы)

2. **3 варианта ответа в параллельных карточках**:
   - Рациональный (синий бордер) — цифры, факты, ROI
   - Эмпатичный (зелёный бордер) — понимание, мягкая альтернатива
   - Перехват инициативы (терракотовый бордер) — закрытие на действие

3. **Per-variant feedback** — кнопки 👍/👎 на каждом варианте, привязанные к конкретным case_ids

4. **Side panel**:
   - Статистика сессии (кейсов в базе / средний success / использовано / сработало)
   - Кейс в фокусе (при клике на кейс в RAG-индикаторе — детали справа)
   - Очередь ревью (кейсы с quality < 30%)
   - CTA «Предложить кейс» (менеджер → форма → технолог)

5. **Context chips** над чатом: Toyota Hilux Surf · Gazpromneft Super 5W-30 · B2B автопарк

## 🚀 Шаги интеграции

### Шаг 1. Применить обновлённую миграцию

```bash
# Если таблица objection_cases уже есть из v1 — дропаем и пересоздаём
psql -d gsm -c "DROP TABLE IF EXISTS objection_cases CASCADE; DROP TYPE IF EXISTS objection_category CASCADE; DROP TYPE IF EXISTS objection_outcome CASCADE; DROP TYPE IF EXISTS customer_segment CASCADE;"

psql -d gsm -f download/sales-copilot-ui/migration_objection_cases_v2.sql

# Залить 100 кейсов из sales-copilot-rag/objection_cases.sql (v1-формат совместим)
psql -d gsm -f download/sales-copilot-rag/objection_cases.sql
```

### Шаг 2. Создать Qdrant collection с named vectors

```bash
curl -X PUT http://localhost:6333/collections/sales_objections \
  -H 'Content-Type: application/json' \
  -d '{
    "vectors": {
      "default": {"size": 384, "distance": "Cosine"},
      "response": {"size": 384, "distance": "Cosine"}
    },
    "optimizers_config": {"default_segment_number": 2, "indexing_threshold": 20000},
    "on_disk_payload": true
  }'
```

### Шаг 3. Установить зависимости

```bash
pip install sentence-transformers redis.asyncio
# bge-reranker-base (180 MB) загрузится автоматически при первом использовании
```

### Шаг 4. Скопировать hybrid_search.py

```bash
cp download/sales-copilot-ui/hybrid_search.py backend/app/services/hybrid_search.py
```

### Шаг 5. Обновить Sales Copilot backend

В `backend/app/services/sales_copilot.py`:

```python
from app.services.hybrid_search import hybrid_search

async def handle_objection(self, objection: str, ...):
    # 1. Hybrid search вместо чисто векторного
    search_result = await hybrid_search(
        query=objection,
        tenant_id=tenant_id,
        db=db,
        category=category,
        customer_segment=customer_segment,
        limit=5,
        min_score=0.55,
        use_reranker=True,
    )

    # 2. SENDING structured SSE events
    yield f"data: {json.dumps({'type': 'rag_cases', 'cases': [...]})}\n\n"

    # 3. Для каждого варианта ответа:
    yield f"data: {json.dumps({'type': 'variant_start', 'variant': 'rational', 'case_ids': [...]})}\n\n"
    async for chunk in llm_stream(...):
        yield f"data: {json.dumps({'type': 'variant_chunk', 'variant': 'rational', 'chunk': chunk})}\n\n"
    yield f"data: {json.dumps({'type': 'variant_done', 'variant': 'rational'})}\n\n"
    # ... повторить для empathetic и take_charge

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
```

### Шаг 6. Скопировать SalesCopilotChat.tsx

```bash
cp download/sales-copilot-ui/SalesCopilotChat.tsx frontend/components/SalesCopilotChat.tsx
```

В `frontend/app/dashboard/sales/page.tsx`:

```tsx
import { SalesCopilotChat } from '@/components/SalesCopilotChat';

export default function SalesPage() {
  return (
    <SalesCopilotChat
      apiUrl="/api/v1/sales/handle-objection"
      feedbackUrl="/api/v1/sales/objection-cases"
      user={{
        id: user.id,
        name: user.name,
        initials: user.name.slice(0, 2).toUpperCase(),
        company_id: user.company_id,
      }}
      contextChips={[
        { type: 'brand', label: 'Toyota Hilux Surf' },
        { type: 'product', label: 'Gazpromneft Super 5W-30' },
        { type: 'segment', label: 'B2B автопарк' },
      ]}
    />
  );
}
```

## 🧪 Тестирование

### Юнит-тесты (обязательно)

```python
# backend/tests/test_hybrid_search.py
import pytest
from app.services.hybrid_search import _reciprocal_rank_fusion

def test_rrf_combines_rankings():
    vector = [{"case_id": "a", "score": 0.9}, {"case_id": "b", "score": 0.8}]
    fts = [{"case_id": "b", "score": 0.5}, {"case_id": "c", "score": 0.4}]
    fused = _reciprocal_rank_fusion(vector, fts)
    # b встречается в обоих — должен быть первым
    assert fused[0]["case_id"] == "b"
    # a и c только в одном
    assert {f["case_id"] for f in fused[1:]} == {"a", "c"}
```

### E2E тест

1. Открой `preview.html` в браузере — увидишь готовый UI
2. Запусти backend + Qdrant + PostgreSQL
3. Загрузи 100 кейсов через `objection_cases.sql`
4. Запусти `seed_objection_cases.py` для индексации в Qdrant
5. Открой Sales Copilot в браузере, введи «У вас дорого»
6. **Ожидаемый результат:**
   - RAG-индикатор появляется через 200-500 ms
   - 3 варианта ответа стримятся параллельно
   - Кнопки 👍/👎 работают
   - В side-panel видно статистику

## ⚠️ Известанные компромиссы

1. **Cross-encoder re-ranker добавляет 50-100ms latency**
   - Решение: `use_reranker=False` для очень длинных списков (>20)
   - Или: включать только при `min_score < 0.7` (когда нужны точные топ-3)

2. **Named vectors в Qdrant увеличивают storage на 2x**
   - 100 кейсов × 384 dims × 2 vectors × 4 bytes = ~300 KB
   - На 10 000 кейсов = 30 MB — приемлемо

3. **Temporal decay может «прятать» новые кейсы**
   - Решение: для кейсов с usage_count < 5 использовать `freshness = 1.0`
   - Это даёт новым кейсам «льготный период»

4. **Structured SSE сложнее парсить, чем текстовый стрим**
   - Решение: React-компонент уже это делает, просто используй его

## 🎯 Ожидаемые метрики после внедрения

| Метрика | До (v1) | После (v2) | Улучшение |
|---|---|---|---|
| Precision@5 (топ-5 релевантны) | ~60% | ~85% | +25% |
| Latency p50 | 800ms | 600ms | -25% (cache) |
| Latency p95 | 2000ms | 1500ms | -25% |
| Менеджер доверяет AI | низкое | высокое | RAG-индикатор |
| Конверсия closed_won | ~35% | ~50-55% | +15-20pp |

## 🛣️ Roadmap (post-MVP)

- [ ] **Voice-to-objection** — Yandex SpeechKit / Whisper → авто-вызов Sales Copilot
- [ ] **A/B тестирование промптов** — 2 версии системного промпта, победитель по конверсии
- [ ] **Auto-suggest кейсов** — при вводе возражения в UI, показать топ-3 кейса в реальном времени (debounce 300ms)
- [ ] **Кросс-компания seed sharing** — победители с success_rate > 80% могут стать «глобальными» (is_seed=true для всех)
- [ ] **MCP-сервер для технолога** — добавление кейсов через Claude Desktop / Cursor без UI
- [ ] **Predictive case suggestion** — предзагрузка кейсов на основе открытой карточки клиента
- [ ] **Multi-variant prompt testing** — 5 разных формулировок одного кейса, A/B-выбор лучшей
