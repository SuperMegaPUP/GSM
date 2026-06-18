// =============================================================
// SSE-клиент для стриминга ответов Sales Copilot
// Использует нативный fetch + ReadableStream (не EventSource, т.к. нужен POST)
// =============================================================

export interface ObjectionResponse {
  style: string;
  label: string;
  text: string;
}

interface SSEChunk {
  type: "chunk";
  text: string;
}

interface SSEDone {
  type: "done";
  variants: ObjectionResponse[];
}

interface SSEFallback {
  type: "fallback";
  reason: string;
}

type SSEEvent = SSEChunk | SSEDone | SSEFallback;

/**
 * Отправляет возражение на бэкенд и стримит ответ через SSE.
 * @param objectionText — что возразил клиент
 * @param context — контекст (какое масло предлагаем)
 * @param onChunk — вызывается при каждом чанке текста (эффект печатной машинки)
 * @param onDone — вызывается когда генерация завершена, передаёт 3 варианта
 * @param onError — вызывается при ошибке сети или сервера
 */
export async function streamObjectionResponse(
  objectionText: string,
  context: string,
  onChunk: (text: string) => void,
  onDone: (variants: ObjectionResponse[]) => void,
  onError: (error: string) => void,
): Promise<void> {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300000); // 5 min timeout

    const response = await fetch("/api/v1/sales/handle-objection", {
      signal: controller.signal,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("access_token")}`,
      },
      body: JSON.stringify({
        objection_text: objectionText,
        context: context || undefined,
      }),
    });

    if (!response.ok) {
      clearTimeout(timeoutId);
      const errBody = await response.json().catch(() => ({}));
      const message =
        errBody.detail || `Ошибка сервера: ${response.status} ${response.statusText}`;
      onError(message);
      return;
    }

    if (!response.body) {
      clearTimeout(timeoutId);
      onError("Сервер не вернул тело ответа");
      return;
    }

    // Читаем ReadableStream и парсим SSE-события
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let receivedDone = false;

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Парсим буфер по строкам, ищем полные SSE-события (разделены пустой строкой)
      const lines = buffer.split("\n");
      // Последняя строка может быть неполной — оставляем в буфере
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);

          if (data === "[DONE]") {
            continue;
          }

          try {
            const event: SSEEvent = JSON.parse(data);

            if (event.type === "chunk") {
              onChunk(event.text);
            } else if (event.type === "done") {
              receivedDone = true;
              onDone(event.variants);
            } else if (event.type === "fallback") {
              onError(`LLM недоступен: ${event.reason}`);
            }
          } catch {
            // Если не удалось распарсить JSON — это может быть сырой текст чанка
            if (data.trim()) {
              onChunk(data);
            }
          }
        }
      }
    }

    // Обработка оставшегося буфера
    if (!receivedDone && buffer.startsWith("data: ")) {
      const data = buffer.slice(6);
      if (data !== "[DONE]") {
        try {
          const event: SSEEvent = JSON.parse(data);
          if (event.type === "chunk") onChunk(event.text);
          else if (event.type === "done") {
            receivedDone = true;
            onDone(event.variants);
          }
        } catch {
          if (data.trim()) onChunk(data);
        }
      }
    }

    clearTimeout(timeoutId);

    // Если стрим завершился без done — ошибка
    if (!receivedDone) {
      onError("Соединение прервано до получения полного ответа");
    }
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === "AbortError") {
      onError("Таймаут: модель не ответила за 5 минут");
    } else {
      const message = err instanceof Error ? err.message : "Неизвестная ошибка сети";
      onError(message);
    }
  }
}
