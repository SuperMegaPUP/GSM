/**
 * ============================================================================
 * GSM Sales Copilot — MCP Server for Objection Handling
 * ============================================================================
 *
 * Model Context Protocol (MCP) adapter that gives LLMs tools to:
 *   1. search_objection_cases — semantic search by client's objection
 *   2. get_case_by_id         — fetch specific case for citation
 *   3. list_categories        — show available categories with counts
 *   4. log_response_feedback  — RLHF: record whether AI response helped
 *
 * Architecture:
 *   LLM (vLLM/Ollama with MCP support)
 *      ↓ MCP protocol (stdio)
 *   [This MCP Server]
 *      ↓ HTTP
 *   FastAPI backend (/api/v1/mcp/sales-copilot/*)
 *      ↓
 *   PostgreSQL (objection_cases table)
 *   Qdrant (sales_objections collection)
 *
 * Usage:
 *   npx tsx mcp-objection-server.ts
 *
 * Or register with Claude Desktop / Cursor / Cline:
 *   {
 *     "mcpServers": {
 *       "gsm-sales-copilot": {
 *         "command": "tsx",
 *         "args": ["./mcp-objection-server.ts"],
 *         "env": {
 *           "GSM_API_URL": "http://localhost:8000/api/v1",
 *           "GSM_API_TOKEN": "${GSM_API_TOKEN}"
 *         }
 *       }
 *     }
 *   }
 *
 * Or use with OpenAI-compatible servers that support MCP tool calling:
 *   - Qwen2.5 via vLLM (--enable-mcp)
 *   - DeepSeek via function calling
 *   - Claude via MCP client library
 * ============================================================================
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  type CallToolRequest,
  type ListToolsRequest,
} from '@modelcontextprotocol/sdk/types.js';

// ─── Configuration ──────────────────────────────────────────────
const API_URL = process.env.GSM_API_URL || 'http://localhost:8000/api/v1';
const API_TOKEN = process.env.GSM_API_TOKEN || '';
const TENANT_ID = process.env.GSM_TENANT_ID || ''; // optional override

// ─── Types ──────────────────────────────────────────────────────
interface ObjectionCase {
  id: string;
  number: number;
  category: 'price' | 'quality' | 'logistics' | 'service' | 'brand' | 'business' | 'closing';
  category_label: string;
  objection_text: string;
  response_text: string;
  tags: string[];
  usage_count: number;
  quality_score: number;
  score?: number; // similarity score from Qdrant
}

interface SearchResult {
  cases: ObjectionCase[];
  total: number;
  search_method: 'vector' | 'fts' | 'fallback';
}

// ─── HTTP helper with auth + tenant context ─────────────────────
async function apiCall<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };
  if (API_TOKEN) headers['Authorization'] = `Bearer ${API_TOKEN}`;
  if (TENANT_ID) headers['X-Tenant-Id'] = TENANT_ID;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

// ─── MCP Server setup ───────────────────────────────────────────
const server = new Server(
  { name: 'gsm-sales-copilot', version: '1.0.0' },
  { capabilities: { tools: {} } },
);

// ─── Tool: search_objection_cases ───────────────────────────────
// The primary tool. LLM calls this when client raises an objection.
// Returns top-K semantically similar cases with proven responses.

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'search_objection_cases',
      description: `Ищет в базе знаний GSM похожие кейсы работы с возражениями клиентов по моторным маслам.
Используй этот инструмент ПЕРВЫМ, когда клиент высказывает возражение (по цене, качеству, срокам, бренду и т.д.).
Возвращает 3-5 наиболее релевантных кейсов с проверенными ответами, которые можно адаптировать.

Принцип работы:
1. Семантический поиск в Qdrant (косинусное сходство векторов возражений)
2. Фильтрация по категории (price, quality, logistics, service, brand, business, closing)
3. Опциональная фильтрация по бренду авто или типу масла
4. Fallback на полнотекстовый поиск в PostgreSQL если Qdrant недоступен

Полученные кейсы используй как референс — НЕ копируй дословно. Адаптируй под:
- Конкретного клиента (название, отрасль)
- Конкретный продукт (название масла, спецификации)
- Контекст диалога (предыдущие сообщения)`,
      inputSchema: {
        type: 'object',
        properties: {
          objection: {
            type: 'string',
            description: 'Текст возражения клиента. Можно дословно или перефразированно.',
          },
          category: {
            type: 'string',
            enum: ['price', 'quality', 'logistics', 'service', 'brand', 'business', 'closing'],
            description: 'Категория возражения. Если не уверен — не указывай, поиск пройдёт по всем категориям.',
          },
          car_brand: {
            type: 'string',
            description: 'Бренд автомобиля клиента (если известен). Например: Toyota, Honda. Фильтрует кейсы, специфичные для этого бренда.',
          },
          fluid_type: {
            type: 'string',
            description: 'Тип масла (engine, atf, cvt, gear, hydraulic). Фильтрует кейсы по типу продукта.',
          },
          limit: {
            type: 'number',
            description: 'Количество кейсов в ответе (по умолчанию 5, макс. 10).',
            default: 5,
            minimum: 1,
            maximum: 10,
          },
          min_score: {
            type: 'number',
            description: 'Минимальный порог семантической близости (0..1, по умолчанию 0.6). Кейсы с меньшим score не возвращаются.',
            default: 0.6,
            minimum: 0,
            maximum: 1,
          },
        },
        required: ['objection'],
      },
    },
    {
      name: 'get_case_by_id',
      description: `Получить конкретный кейс по его ID. Используй, когда нужно процитировать конкретный кейс или когда LLM уже знает ID из предыдущего поиска.

Возвращает полный текст возражения и ответа, теги, статистику использования.`,
      inputSchema: {
        type: 'object',
        properties: {
          case_id: {
            type: 'string',
            description: 'ID кейса в формате obj_XXX (например, obj_001).',
          },
        },
        required: ['case_id'],
      },
    },
    {
      name: 'list_categories',
      description: `Показать все категории возражений с количеством кейсов в каждой. Используй в начале диалога или когда не понятно, в какую категорию попадает возражение клиента.`,
      inputSchema: {
        type: 'object',
        properties: {},
      },
    },
    {
      name: 'log_response_feedback',
      description: `Записать обратную связь по качеству сгенерированного ответа (для RLHF и улучшения базы знаний).

Вызывай ПОСЛЕ того, как менеджер использовал твой ответ. Это помогает системе улучшаться со временем:
- positive=true → quality_score кейса повышается, кейс будет чаще предлагаться
- positive=false → quality_score понижается, кейс реже предлагается, попадает в очередь на ревью технологом`,
      inputSchema: {
        type: 'object',
        properties: {
          case_id: {
            type: 'string',
            description: 'ID кейса, который был использован как основа для ответа.',
          },
          positive: {
            type: 'boolean',
            description: 'true — ответ помог менеджеру, false — ответ был бесполезен/нерелевантен.',
          },
          comment: {
            type: 'string',
            description: 'Опциональный комментарий менеджера (что было не так, что улучшить).',
          },
        },
        required: ['case_id', 'positive'],
      },
    },
  ],
}));

// ─── Tool handlers ──────────────────────────────────────────────
server.setRequestHandler(CallToolRequestSchema, async (request: CallToolRequest) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'search_objection_cases':
        return await handleSearch(args);
      case 'get_case_by_id':
        return await handleGetById(args);
      case 'list_categories':
        return await handleListCategories(args);
      case 'log_response_feedback':
        return await handleFeedback(args);
      default:
        return {
          content: [{ type: 'text', text: `Unknown tool: ${name}` }],
          isError: true,
        };
    }
  } catch (err: any) {
    return {
      content: [
        {
          type: 'text',
          text: `Error in tool ${name}: ${err.message}\n\nStack: ${err.stack}`,
        },
      ],
      isError: true,
    };
  }
});

// ─── search_objection_cases handler ─────────────────────────────
async function handleSearch(args: any) {
  const {
    objection,
    category,
    car_brand,
    fluid_type,
    limit = 5,
    min_score = 0.6,
  } = args;

  if (!objection || typeof objection !== 'string') {
    return {
      content: [{ type: 'text', text: 'Параметр objection обязателен и должен быть строкой.' }],
      isError: true,
    };
  }

  // Build query params
  const params = new URLSearchParams({
    q: objection,
    limit: String(Math.min(limit, 10)),
    min_score: String(min_score),
  });
  if (category) params.set('category', category);
  if (car_brand) params.set('car_brand', car_brand);
  if (fluid_type) params.set('fluid_type', fluid_type);

  const result = await apiCall<SearchResult>(
    `/sales/search-objection-cases?${params}`,
    { method: 'GET' }
  );

  if (!result.cases || result.cases.length === 0) {
    return {
      content: [{
        type: 'text',
        text: formatNoResults(objection, category, result.search_method),
      }],
    };
  }

  // Format results for LLM
  const formatted = formatSearchResults(result);
  return {
    content: [{
      type: 'text',
      text: formatted,
    }],
  };
}

// ─── get_case_by_id handler ─────────────────────────────────────
async function handleGetById(args: any) {
  const { case_id } = args;
  if (!case_id) {
    return {
      content: [{ type: 'text', text: 'Параметр case_id обязателен.' }],
      isError: true,
    };
  }

  const caseData = await apiCall<ObjectionCase>(
    `/sales/objection-cases/${encodeURIComponent(case_id)}`,
    { method: 'GET' }
  );

  return {
    content: [{
      type: 'text',
      text: formatSingleCase(caseData),
    }],
  };
}

// ─── list_categories handler ────────────────────────────────────
async function handleListCategories(_args: any) {
  const cats = await apiCall<Array<{
    category: string;
    category_label: string;
    count: number;
  }>>('/sales/objection-categories');

  let text = '📋 Категории возражений в базе знаний GSM:\n\n';
  for (const c of cats) {
    text += `• **${c.category_label}** (\`${c.category}\`) — ${c.count} кейсов\n`;
  }
  text += '\nИспользуй параметр `category` в `search_objection_cases` для фильтрации.';

  return { content: [{ type: 'text', text }] };
}

// ─── log_response_feedback handler ──────────────────────────────
async function handleFeedback(args: any) {
  const { case_id, positive, comment } = args;
  if (!case_id || typeof positive !== 'boolean') {
    return {
      content: [{ type: 'text', text: 'Параметры case_id и positive обязательны.' }],
      isError: true,
    };
  }

  await apiCall(`/sales/objection-cases/${encodeURIComponent(case_id)}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ positive, comment }),
  });

  return {
    content: [{
      type: 'text',
      text: `✅ Обратная связь записана для кейса ${case_id}.\n` +
            `Кейс ${positive ? 'повышен' : 'понижен'} в ранжировании.\n` +
            (comment ? `Комментарий: "${comment}"` : ''),
    }],
  };
}

// ─── Formatters ─────────────────────────────────────────────────

function formatSearchResults(result: SearchResult): string {
  const { cases, search_method, total } = result;

  let text = `🔍 Найдено ${cases.length} из ${total} релевантных кейсов`;
  text += ` (метод: ${search_method === 'vector' ? 'векторный поиск' : search_method === 'fts' ? 'полнотекстовый' : 'fallback'})\n\n`;

  text += '════════════════════════════════════════════════════════════\n\n';

  cases.forEach((c, i) => {
    text += `### Кейс ${i + 1} из ${cases.length}\n`;
    text += `**ID:** \`${c.id}\`  |  **Категория:** ${c.category_label}\n`;
    text += `**Релевантность:** ${(c.score ? c.score * 100 : 0).toFixed(0)}%\n`;
    text += `**Использовался ранее:** ${c.usage_count} раз(а)\n\n`;

    text += `**💬 Возражение клиента:**\n> ${c.objection_text}\n\n`;

    text += `**✅ Рекомендованный ответ:**\n${c.response_text}\n\n`;

    if (c.tags && c.tags.length > 0) {
      text += `**🏷️ Теги:** ${c.tags.map(t => `\`${t}\``).join(', ')}\n\n`;
    }

    text += '────────────────────────────────────────────────────────────\n\n';
  });

  text += '════════════════════════════════════════════════════════════\n';
  text += '📌 **Инструкция для LLM:**\n';
  text += '1. Проанализируй все кейсы выше — они проверены технологами GSM.\n';
  text += '2. Выбери 1-2 наиболее релевантных текущему возражению.\n';
  text += '3. **Адаптируй под контекст клиента** — не копируй дословно.\n';
  text += '4. Подставь реальные данные: название масла, спецификации, цены, сроки.\n';
  text += '5. Сгенерируй 3 варианта ответа:\n';
  text += '   - **Рациональный** — цифры, факты, расчёт окупаемости\n';
  text += '   - **Эмпатичный** — понимание позиции клиента, мягкая альтернатива\n';
  text += '   - **Перехват инициативы** — закрытие на следующее действие\n';
  text += '6. После использования ответа менеджером, вызови `log_response_feedback` с оценкой.\n';

  return text;
}

function formatSingleCase(c: ObjectionCase): string {
  let text = `📋 **Кейс ${c.id}** — ${c.category_label}\n\n`;
  text += `**💬 Возражение:**\n> ${c.objection_text}\n\n`;
  text += `**✅ Ответ:**\n${c.response_text}\n\n`;
  if (c.tags && c.tags.length > 0) {
    text += `**🏷️ Теги:** ${c.tags.map(t => `\`${t}\``).join(', ')}\n\n`;
  }
  text += `**Статистика:**\n`;
  text += `- Использований: ${c.usage_count}\n`;
  text += `- Качество: ${(c.quality_score * 100).toFixed(0)}%\n`;
  return text;
}

function formatNoResults(objection: string, category: string | undefined, method: string): string {
  let text = `🔍 Поиск по возражению "${objection}" не дал результатов`;
  if (category) text += ` в категории "${category}"`;
  text += ` (метод: ${method}).\n\n`;

  text += '💡 **Рекомендации:**\n';
  text += '1. Переформулируй возражение — возможно, использованы специфические термины.\n';
  text += '2. Убери параметр category — поиск пройдёт по всем категориям.\n';
  text += '3. Снизь min_score (например, до 0.4) — вернутся менее релевантные кейсы.\n';
  text += '4. Используй `list_categories` чтобы увидеть доступные категории.\n\n';

  text += '⚠️ Если запросил менеджер — сообщи ему, что кейса нет в базе. ';
  text += 'Это сигнал технологу добавить новый кейс через интерфейс импорта.';
  return text;
}

// ─── Run server ─────────────────────────────────────────────────
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('[GSM MCP] Sales Copilot MCP server started on stdio');
  console.error(`[GSM MCP] API URL: ${API_URL}`);
  console.error(`[GSM MCP] Tenant: ${TENANT_ID || '(from JWT)'}`);
}

main().catch((err) => {
  console.error('[GSM MCP] Fatal:', err);
  process.exit(1);
});
