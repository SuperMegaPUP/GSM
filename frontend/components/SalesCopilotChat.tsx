'use client';

/**
 * ============================================================================
 * GSM Sales Copilot 2.0 — Chat Component with RAG Indicator
 * ============================================================================
 *
 * Key features:
 *   - SSE streaming for real-time AI response
 *   - RAG indicator showing retrieved cases BEFORE the answer
 *   - 3 response variants (rational / empathetic / take-charge) rendered in
 *     parallel as structured chunks arrive
 *   - Per-variant feedback buttons (👍/👎) for RLHF
 *   - Side panel with: stats, selected case preview, RLHF queue,
 *     "suggest new case" CTA
 *
 * Usage:
 *   <SalesCopilotChat
 *     apiUrl="/api/v1/sales/handle-objection"
 *     feedbackUrl="/api/v1/sales/objection-cases"
 *     user={{ id, name, initials, company_id }}
 *     contextChips={[{type:'brand', label:'Toyota Hilux Surf'}, ...]}
 *   />
 */

import { motion, AnimatePresence } from 'framer-motion';
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react';

// ─── Types ──────────────────────────────────────────────────────
interface User {
  id: string;
  name: string;
  initials: string;
  company_id: string;
}

interface ContextChip {
  type: 'brand' | 'product' | 'segment';
  label: string;
}

interface RagCase {
  case_id: string;
  score: number;
  category: string;
  category_label: string;
  objection_text: string;
  search_method: 'vector' | 'fts' | 'hybrid';
}

interface ResponseVariant {
  variant: 'rational' | 'empathetic' | 'take_charge';
  text: string;
  case_ids: string[];
  streaming?: boolean;
}

interface Message {
  id: string;
  role: 'user' | 'ai';
  author: string;
  text?: string;
  thinking?: boolean;
  rag_cases?: RagCase[];
  variants?: ResponseVariant[];
  timestamp: string;
}

interface SalesCopilotChatProps {
  apiUrl: string;
  feedbackUrl: string;
  user: User;
  contextChips?: ContextChip[];
}

// ─── Constants ──────────────────────────────────────────────────
const VARIANT_CONFIG = {
  rational: {
    label: 'Рациональный',
    color: 'var(--info)',
    icon: 'M3 3v18h18M19 9l-5 5-4-4-3 3',
  },
  empathetic: {
    label: 'Эмпатичный',
    color: 'var(--success)',
    icon: 'M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.29 1.51 4.04 3 5.5l7 7Z',
  },
  take_charge: {
    label: 'Перехват инициативы',
    color: 'var(--accent)',
    icon: 'M13 2L3 14h9l-1 8 10-12h-9l1-8z',
  },
} as const;

// ─── Component ──────────────────────────────────────────────────
export function SalesCopilotChat({
  apiUrl,
  feedbackUrl,
  user,
  contextChips = [],
}: SalesCopilotChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'greeting',
      role: 'ai',
      author: 'Sales Copilot · готов к работе',
      text: 'Привет! Я помогу отработать любое возражение клиента. Введи, что он сказал — я найду похожие кейсы в базе знаний компании и предложу 3 варианта ответа.',
      timestamp: new Date().toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
      }),
    },
  ]);
  const [input, setInput] = useState('');
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [feedbackLogged, setFeedbackLogged] = useState<
    Record<string, 'positive' | 'negative'>
  >({});

  const messagesRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
    }
  }, [messages]);

  // Auto-grow textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        120,
      )}px`;
    }
  }, [input]);

  // ─── Send message + stream response ─────────────────────────
  const sendMessage = useCallback(async () => {
    const text = input.trim();
    if (!text) return;

    const now = new Date().toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
    });

    // Add user message
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      author: `${user.name} · ${now}`,
      text,
      timestamp: now,
    };
    setMessages((m) => [...m, userMsg]);
    setInput('');

    // Add AI "thinking" message
    const aiMsgId = `ai-${Date.now()}`;
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'ai',
      author: 'Sales Copilot · анализирует…',
      thinking: true,
      timestamp: now,
    };
    setMessages((m) => [...m, aiMsg]);

    // Stream response via SSE
    try {
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: JSON.stringify({
          objection: text,
          context_chips: contextChips,
        }),
      });

      if (!response.ok) {
        const errBody = await response.text();
        throw new Error(errBody || `HTTP ${response.status}`);
      }
      if (!response.body) throw new Error('No response body');

      // Parse SSE stream
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr || jsonStr === '[DONE]') continue;

          try {
            const evt = JSON.parse(jsonStr);
            handleSSEEvent(evt, aiMsgId);
          } catch (e) {
            console.warn('Failed to parse SSE chunk:', e);
          }
        }
      }
    } catch (err) {
      console.error('Sales Copilot request failed:', err);
      setMessages((m) =>
        m.map((msg) =>
          msg.id === aiMsgId
            ? {
                ...msg,
                thinking: false,
                text: '⚠️ Не удалось получить ответ. Проверьте подключение к серверу.',
              }
            : msg,
        ),
      );
    }
  }, [apiUrl, input, user.name, contextChips]);

  // ─── Handle structured SSE events ───────────────────────────
  const handleSSEEvent = useCallback(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (evt: Record<string, any>, msgId: string) => {
      switch (evt.type) {
        case 'rag_cases':
          setMessages((m) =>
            m.map((msg) =>
              msg.id === msgId
                ? {
                    ...msg,
                    thinking: false,
                    rag_cases: evt.cases,
                    author: 'Sales Copilot · формулирует ответ…',
                  }
                : msg,
            ),
          );
          break;

        case 'variant_start':
          // Begin streaming a response variant
          setMessages((m) =>
            m.map((msg) =>
              msg.id === msgId
                ? {
                    ...msg,
                    variants: [
                      ...(msg.variants || []),
                      {
                        variant: evt.variant,
                        text: '',
                        case_ids: evt.case_ids || [],
                        streaming: true,
                      },
                    ],
                  }
                : msg,
            ),
          );
          break;

        case 'variant_chunk':
          // Append chunk to streaming variant
          setMessages((m) =>
            m.map((msg) => {
              if (msg.id !== msgId || !msg.variants) return msg;
              return {
                ...msg,
                variants: msg.variants.map((v) =>
                  v.variant === evt.variant
                    ? { ...v, text: v.text + evt.chunk }
                    : v,
                ),
              };
            }),
          );
          break;

        case 'variant_done':
          // Mark variant as complete
          setMessages((m) =>
            m.map((msg) => {
              if (msg.id !== msgId || !msg.variants) return msg;
              return {
                ...msg,
                variants: msg.variants.map((v) =>
                  v.variant === evt.variant ? { ...v, streaming: false } : v,
                ),
              };
            }),
          );
          break;

        case 'done':
          setMessages((m) =>
            m.map((msg) =>
              msg.id === msgId
                ? { ...msg, author: 'Sales Copilot · ответ готов' }
                : msg,
            ),
          );
          break;

        case 'error':
          setMessages((m) =>
            m.map((msg) =>
              msg.id === msgId
                ? {
                    ...msg,
                    thinking: false,
                    text: `⚠️ ${evt.message || 'Ошибка генерации'}`,
                  }
                : msg,
            ),
          );
          break;
      }
    },
    [],
  );

  // ─── Feedback (RLHF) ────────────────────────────────────────
  const logFeedback = useCallback(
    async (caseId: string, positive: boolean) => {
      // Optimistic UI
      setFeedbackLogged((prev) => ({
        ...prev,
        [`${caseId}-${positive}`]: positive ? 'positive' : 'negative',
      }));

      try {
        await fetch(`${feedbackUrl}/${caseId}/feedback`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${localStorage.getItem('access_token')}`,
          },
          body: JSON.stringify({
            outcome: positive ? 'closed_won' : 'closed_lost',
          }),
        });
      } catch (e) {
        console.warn('Failed to log feedback:', e);
      }
    },
    [feedbackUrl],
  );

  // ─── Keyboard handler ───────────────────────────────────────
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // ─── Render ─────────────────────────────────────────────────
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      {/* Chat panel */}
      <div
        className="flex flex-col overflow-hidden rounded-xl border bg-[var(--surface-1)]"
        style={{ height: 'calc(100vh - 180px)', minHeight: 600 }}
      >
        {/* Header */}
        <header
          className="flex items-center justify-between gap-4 border-b px-6 py-4"
          style={{ background: 'var(--surface-2)' }}
        >
          <div className="flex items-center gap-3">
            <div
              className="grid h-9 w-9 place-items-center rounded-md text-[var(--primary-foreground)]"
              style={{
                background:
                  'linear-gradient(135deg, var(--primary), var(--accent))',
                boxShadow: 'var(--shadow-md)',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <rect width="18" height="10" x="3" y="11" rx="2" />
                <circle cx="12" cy="5" r="2" />
                <path d="M12 7v4" />
              </svg>
            </div>
            <div>
              <div className="text-base font-semibold tracking-tight">
                Sales Copilot
              </div>
              <div className="flex items-center gap-1.5 text-xs text-[var(--sidebar-muted)]">
                <span
                  className="inline-block h-1.5 w-1.5 rounded-full"
                  style={{
                    background: 'var(--success)',
                    boxShadow: '0 0 8px var(--success)',
                  }}
                />
                Online · RAG активен
              </div>
            </div>
          </div>
          <div className="hidden gap-3 text-xs text-[var(--sidebar-muted)] sm:flex">
            <span>Менеджер: <span className="font-mono">{user.name}</span></span>
          </div>
        </header>

        {/* Context chips */}
        {contextChips.length > 0 && (
          <div
            className="flex flex-wrap gap-1.5 px-6 py-3"
            style={{ background: 'var(--surface-2)' }}
          >
            {contextChips.map((chip, i) => (
              <span
                key={i}
                className={`context-chip context-chip--${chip.type}`}
              >
                {chip.label}
              </span>
            ))}
          </div>
        )}

        {/* Messages */}
        <div ref={messagesRef} className="flex-1 space-y-4 overflow-y-auto p-6">
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
                className={`flex gap-3 ${
                  msg.role === 'user' ? 'flex-row-reverse' : ''
                }`}
                style={{ maxWidth: '85%', marginLeft: msg.role === 'user' ? 'auto' : 0 }}
              >
                {/* Avatar */}
                <div
                  className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full text-xs font-semibold"
                  style={{
                    background:
                      msg.role === 'user'
                        ? 'var(--primary)'
                        : 'linear-gradient(135deg, var(--accent), var(--primary))',
                    color: 'var(--primary-foreground)',
                  }}
                >
                  {msg.role === 'user' ? user.initials : 'AI'}
                </div>

                <div className="flex min-w-0 flex-1 flex-col gap-1.5">
                  <div className="text-xs font-medium text-[var(--sidebar-muted)]">
                    {msg.author}
                  </div>

                  {/* Plain text bubble */}
                  {msg.text && (
                    <div
                      className="rounded-lg px-4 py-3 text-sm"
                      style={{
                        background:
                          msg.role === 'user'
                            ? 'var(--primary)'
                            : 'var(--surface-2)',
                        color:
                          msg.role === 'user'
                            ? 'var(--primary-foreground)'
                            : 'var(--foreground)',
                        border:
                          msg.role === 'ai'
                            ? '1px solid var(--border)'
                            : 'none',
                        borderBottomRightRadius:
                          msg.role === 'user' ? 'var(--radius-xs)' : undefined,
                        borderBottomLeftRadius:
                          msg.role === 'ai' ? 'var(--radius-xs)' : undefined,
                      }}
                    >
                      {msg.text}
                    </div>
                  )}

                  {/* Thinking indicator */}
                  {msg.thinking && (
                    <div
                      className="rounded-lg border px-4 py-3"
                      style={{
                        background: 'var(--surface-2)',
                        borderColor: 'var(--border)',
                      }}
                    >
                      <div className="flex gap-1">
                        {[0, 1, 2].map((i) => (
                          <span
                            key={i}
                            className="typing-dot"
                            style={{ animationDelay: `${i * 0.2}s` }}
                          />
                        ))}
                      </div>
                      <div className="mt-1 text-xs text-[var(--sidebar-muted)]">
                        Векторный поиск · гибридный matcher · re-ranking
                      </div>
                    </div>
                  )}

                  {/* RAG indicator */}
                  {msg.rag_cases && msg.rag_cases.length > 0 && (
                    <RagIndicator
                      cases={msg.rag_cases}
                      onSelect={setSelectedCaseId}
                      selectedId={selectedCaseId}
                    />
                  )}

                  {/* Response variants */}
                  {msg.variants && msg.variants.length > 0 && (
                    <div className="space-y-3">
                      {msg.variants.map((v) => (
                        <ResponseVariantCard
                          key={v.variant}
                          variant={v}
                          feedbackLogged={feedbackLogged}
                          onFeedback={logFeedback}
                          onCopy={(text) => navigator.clipboard.writeText(text)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>

        {/* Input area */}
        <div
          className="border-t px-6 py-4"
          style={{ background: 'var(--surface-2)' }}
        >
          <div className="flex items-end gap-3">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Что сказал клиент? Например: «Дорого, на Авито дешевле»…"
              rows={1}
              className="flex-1 resize-none rounded-lg border px-4 py-3 text-sm outline-none transition-all placeholder:text-[var(--sidebar-muted)] focus:border-[var(--primary)] focus:shadow-[var(--shadow-glow)]"
              style={{
                background: 'var(--surface-1)',
                borderColor: 'var(--border)',
                color: 'var(--foreground)',
                minHeight: 44,
                maxHeight: 120,
              }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim()}
              className="inline-flex items-center gap-1.5 rounded-lg px-5 py-3 text-sm font-medium transition-all disabled:cursor-not-allowed disabled:opacity-50"
              style={{
                background: 'var(--primary)',
                color: 'var(--primary-foreground)',
                boxShadow: 'var(--shadow-sm)',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
              </svg>
              Отправить
            </button>
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-[var(--sidebar-muted)]">
            <div className="flex items-center gap-1.5">
              <kbd className="kbd">⏎</kbd> отправить ·{' '}
              <kbd className="kbd">Shift+⏎</kbd> перенос строки
            </div>
          </div>
        </div>
      </div>

      {/* Side panel */}
      <SidePanel
        selectedCaseId={selectedCaseId}
      />
    </div>
  );
}

// ============================================================================
// RAG Indicator subcomponent
// ============================================================================

function RagIndicator({
  cases,
  onSelect,
  selectedId,
}: {
  cases: RagCase[];
  onSelect: (id: string) => void;
  selectedId: string | null;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24 }}
      className="rounded-md border p-3"
      style={{
        background:
          'linear-gradient(135deg, var(--info-muted), var(--primary-muted))',
        borderColor: 'var(--info)',
      }}
    >
      <div
        className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide"
        style={{ color: 'var(--info)' }}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        RAG · Найдено {cases.length} релевантных кейсов
      </div>
      <div className="mb-2 text-xs font-medium">Эти кейсы легли в основу ответа ↓</div>
      <div className="space-y-2">
        {cases.map((c) => (
          <button
            key={c.case_id}
            onClick={() => onSelect(c.case_id)}
            className="flex w-full items-center gap-2 rounded-sm border px-2.5 py-2 text-left text-xs transition-all hover:translate-x-0.5"
            style={{
              background: selectedId === c.case_id ? 'var(--surface-3)' : 'var(--surface-1)',
              borderColor: selectedId === c.case_id ? 'var(--info)' : 'var(--border)',
            }}
          >
            <span
              className="flex-shrink-0 rounded-xs px-1.5 py-0.5 font-mono text-[11px] font-semibold"
              style={{
                background: 'var(--info-muted)',
                color: 'var(--info)',
              }}
            >
              {Math.round(c.score * 100)}%
            </span>
            <span className="flex-shrink-0 text-[10px] uppercase tracking-wide text-[var(--sidebar-muted)]">
              {c.category_label.slice(0, 12)}
            </span>
            <span className="flex-1 truncate text-[var(--foreground)]">
              {c.objection_text}
            </span>
            <span
              className="flex-shrink-0 rounded-xs px-1.5 py-0.5 text-[10px] font-medium"
              style={{
                background: c.search_method === 'hybrid' ? 'var(--accent-muted)' : 'var(--primary-muted)',
                color: c.search_method === 'hybrid' ? 'var(--accent)' : 'var(--primary)',
              }}
            >
              {c.search_method}
            </span>
          </button>
        ))}
      </div>
    </motion.div>
  );
}

// ============================================================================
// Response Variant subcomponent
// ============================================================================

function ResponseVariantCard({
  variant,
  feedbackLogged,
  onFeedback,
  onCopy,
}: {
  variant: ResponseVariant;
  feedbackLogged: Record<string, 'positive' | 'negative'>;
  onFeedback: (caseId: string, positive: boolean) => void;
  onCopy: (text: string) => void;
}) {
  const cfg = VARIANT_CONFIG[variant.variant];

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24 }}
      className="rounded-md border-l-[3px] border p-3.5"
      style={{
        background: 'var(--surface-1)',
        borderColor: 'var(--border)',
        borderLeftColor: cfg.color,
      }}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span
          className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide"
          style={{ color: cfg.color }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d={cfg.icon} />
          </svg>
          {cfg.label}
          {variant.streaming && (
            <span className="ml-1 inline-block h-1 w-1 animate-pulse rounded-full" style={{ background: cfg.color }} />
          )}
        </span>
        {variant.case_ids.length > 0 && (
          <span className="text-[10px] text-[var(--sidebar-muted)]">
            based on {variant.case_ids.join(', ')}
          </span>
        )}
      </div>
      <div className="text-sm leading-relaxed">{variant.text}</div>

      {!variant.streaming && variant.text && (
        <div className="mt-3 flex gap-1.5 border-t border-dashed border-[var(--border)] pt-3">
          <button
            onClick={() => onCopy(variant.text)}
            className="action-btn"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="9" y="9" width="13" height="13" rx="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
            Скопировать
          </button>
          {variant.case_ids.map((cid) => (
            <span key={cid} className="flex gap-1.5">
              <button
                onClick={() => onFeedback(cid, true)}
                className={`action-btn action-btn--positive ${
                  feedbackLogged[`${cid}-true`] === 'positive' ? 'action-btn--used' : ''
                }`}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M7 10v12M15 5.88L14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z" />
                </svg>
                Сработало
              </button>
              <button
                onClick={() => onFeedback(cid, false)}
                className={`action-btn action-btn--negative ${
                  feedbackLogged[`${cid}-false`] === 'negative' ? 'action-btn--used' : ''
                }`}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <path d="M17 14V2M9 18.12L10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z" />
                </svg>
                Не сработало
              </button>
            </span>
          ))}
        </div>
      )}
    </motion.div>
  );
}

// ============================================================================
// Side Panel (stats + case preview + RLHF queue)
// ============================================================================

function SidePanel({
  selectedCaseId,
}: {
  selectedCaseId: string | null;
}) {
  return (
    <aside className="flex flex-col gap-4">
      <div className="rounded-lg border bg-[var(--surface-1)] p-4">
        <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--sidebar-muted)]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2">
            <path d="M3 3v18h18M19 9l-5 5-4-4-3 3" />
          </svg>
          Статистика сессии
        </div>
        <div className="grid grid-cols-2 gap-2">
          {[
            { label: 'Кейсов в базе', value: '100', delta: '+0 сегодня' },
            { label: 'Средний success', value: '68%', delta: '↑ +4% за неделю' },
            { label: 'Использовано', value: '847', delta: '↑ +12 за день' },
            { label: 'Сработало', value: '572', delta: '67% конверсия' },
          ].map((s) => (
            <div key={s.label} className="rounded-md bg-[var(--surface-2)] p-2.5">
              <div className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--sidebar-muted)]">
                {s.label}
              </div>
              <div className="font-mono text-lg font-semibold leading-none">
                {s.value}
              </div>
              <div className="mt-0.5 text-[10px] text-[var(--success)]">{s.delta}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border bg-[var(--surface-1)] p-4">
        <div className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--sidebar-muted)]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          Кейс в фокусе
        </div>
        <div className="text-xs">
          {selectedCaseId ? (
            <div>Выбран: <span className="font-mono">{selectedCaseId}</span></div>
          ) : (
            <div className="text-[var(--sidebar-muted)]">
              Нажми на кейс в RAG-индикаторе, чтобы увидеть детали.
            </div>
          )}
        </div>
      </div>

      <div
        className="rounded-lg border p-4"
        style={{
          background:
            'linear-gradient(135deg, var(--accent-muted), var(--primary-muted))',
          borderColor: 'var(--accent)',
        }}
      >
        <div
          className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide"
          style={{ color: 'var(--accent)' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Предложить кейс
        </div>
        <div className="mb-3 text-xs leading-relaxed">
          Был удачный ответ, которого нет в базе? Отправь — технолог проверит и
          опубликует.
        </div>
        <button
          className="action-btn w-full justify-center"
          style={{
            background: 'var(--accent)',
            color: 'var(--accent-foreground)',
            borderColor: 'var(--accent)',
          }}
        >
          + Новый кейс
        </button>
      </div>
    </aside>
  );
}
