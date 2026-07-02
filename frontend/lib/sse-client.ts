export interface ObjectionResponse {
  style: string;
  label: string;
  text: string;
}

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
  let timeoutId: NodeJS.Timeout | undefined;
  try {
    const controller = new AbortController();
    timeoutId = setTimeout(() => controller.abort(), 300000);

    const response = await fetch("/api/v1/sales/handle-objection", {
      signal: controller.signal,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("access_token")}`,
      },
      body: JSON.stringify({
        objection: objectionText,
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

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let receivedDone = false;

    // Аккумуляция вариантов из последовательности variant_start → variant_chunk → variant_done
    const variantLabels: Record<string, string> = {
      rational: "Рациональный",
      empathetic: "Эмпатичный",
      take_charge: "Перехват инициативы",
    };
    const accumulated: Record<string, string> = {};

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);

          if (data === "[DONE]") {
            continue;
          }

          try {
            const event = JSON.parse(data);
            const type = event.type;

            if (type === "variant_chunk") {
              const v = event.variant as string;
              const chunk = event.chunk as string;
              if (chunk) {
                accumulated[v] = (accumulated[v] || "") + chunk;
                onChunk(chunk);
              }
            } else if (type === "variant_done") {
              // Вариант завершён — ничего не делаем, ждём финальный done
            } else if (type === "rag_cases") {
              // Пропускаем, не показываем в упрощённом режиме
            } else if (type === "done") {
              receivedDone = true;
              // Собираем 3 варианта
              const variants: ObjectionResponse[] = Object.entries(accumulated)
                .filter((entry) => entry[1].trim().length > 0)
                .map(([style, text]) => ({
                  style,
                  label: variantLabels[style] || style,
                  text: text.trim(),
                }));
              if (variants.length === 0) {
                onError("Модель не сгенерировала ответы");
              } else {
                onDone(variants);
              }
            } else if (type === "error") {
              onError(event.message || "Неизвестная ошибка");
            } else if (type === "fallback") {
              onError(`LLM недоступен: ${event.reason}`);
            }
          } catch {
            if (data.trim()) {
              onChunk(data);
            }
          }
        }
      }
    }

    if (timeoutId) clearTimeout(timeoutId);

    if (!receivedDone) {
      onError("Соединение прервано до получения полного ответа");
    }
  } catch (err: unknown) {
    if (timeoutId) clearTimeout(timeoutId);
    if (err instanceof DOMException && err.name === "AbortError") {
      onError("Таймаут: модель не ответила за 5 минут");
    } else {
      const message = err instanceof Error ? err.message : "Неизвестная ошибка сети";
      onError(message);
    }
  }
}
