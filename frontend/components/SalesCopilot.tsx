// =============================================================
// Sales Copilot — виджет для отработки возражений клиентов
// Использует SSE-стриминг от бэкенда для генерации 3 вариантов ответов
// =============================================================

"use client";

import React, { useState, useRef } from "react";
import { toast } from "sonner";
import { Bot, Copy, Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { streamObjectionResponse, type ObjectionResponse } from "@/lib/sse-client";

// =============================================================
// Конфигурация стилей ответов
// =============================================================

const VARIANT_CONFIG = {
  empathic: {
    icon: "🤝",
    title: "Эмпатичный ответ",
    description: "Понимание и мягкое переубеждение",
    borderColor: "border-blue-200",
    bgHover: "hover:border-blue-300",
  },
  rational: {
    icon: "🧠",
    title: "Рациональный ответ",
    description: "Цифры, факты, расчёты",
    borderColor: "border-emerald-200",
    bgHover: "hover:border-emerald-300",
  },
  assertive: {
    icon: "⚡",
    title: "Перехват инициативы",
    description: "Предложение действия (тест, пробник)",
    borderColor: "border-amber-200",
    bgHover: "hover:border-amber-300",
  },
};

// =============================================================
// Карточка варианта ответа
// =============================================================

function VariantCard({ variant }: { variant: ObjectionResponse }) {
  const [copied, setCopied] = useState(false);
  const config = VARIANT_CONFIG[variant.style as keyof typeof VARIANT_CONFIG];

  const handleCopy = () => {
    navigator.clipboard.writeText(variant.text);
    setCopied(true);
    toast.success("Ответ скопирован в буфер обмена");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card className={`transition-all ${config?.borderColor || "border-gray-200"} ${config?.bgHover || ""}`}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base flex items-center gap-2">
              {config?.icon} {config?.title || variant.label}
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
              {config?.description}
            </p>
          </div>
          <Badge variant="outline" className="text-xs">
            {variant.style}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg bg-muted/50 p-4 mb-3 min-h-[80px]">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{variant.text}</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={handleCopy}
          disabled={copied}
        >
          <Copy className="mr-2 h-4 w-4" />
          {copied ? "Скопировано!" : "📋 Скопировать"}
        </Button>
      </CardContent>
    </Card>
  );
}

// =============================================================
// Основной виджет Sales Copilot
// =============================================================

export interface SalesCopilotProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialContext?: string;
  variant?: "dialog" | "page";
}

export function SalesCopilot({
  open,
  onOpenChange,
  initialContext = "",
  variant = "dialog",
}: SalesCopilotProps) {
  const [objection, setObjection] = useState("");
  const [context, setContext] = useState(initialContext);
  const [streaming, setStreaming] = useState(false);
  const [fullText, setFullText] = useState("");
  const [variants, setVariants] = useState<ObjectionResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Обновляем контекст при изменении пропса
  React.useEffect(() => {
    if (open && initialContext) {
      setContext(initialContext);
    }
  }, [open, initialContext]);

  const handleGenerate = async () => {
    if (!objection.trim()) {
      toast.error("Введите возражение клиента");
      textareaRef.current?.focus();
      return;
    }

    setStreaming(true);
    setFullText("");
    setVariants([]);
    setError(null);

    try {
      await streamObjectionResponse(
        objection.trim(),
        context.trim(),
        // onChunk — накапливаем текст для эффекта печатной машинки
        (text: string) => {
          setFullText((prev) => prev + text);
        },
        // onDone — получаем 3 финальных варианта
        (resultVariants: ObjectionResponse[]) => {
          setVariants(resultVariants);
          setStreaming(false);
        },
        // onError
        (err: string) => {
          setError(err);
          toast.error(err);
          setStreaming(false);
        },
      );
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Неизвестная ошибка";
      setError(message);
      toast.error(message);
      setStreaming(false);
    }
  };

  const handleReset = () => {
    setObjection("");
    setContext(initialContext);
    setFullText("");
    setVariants([]);
    setError(null);
  };

  const isDialog = variant === "dialog";

  // =============================================================
  // Рендер контента виджета (переиспользуется в Dialog и на странице)
  // =============================================================

  const renderContent = () => (
    <div className="space-y-4">
      {/* Поле возражения */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Что возразил клиент?</label>
        <Textarea
          ref={textareaRef}
          placeholder={"Например: &quot;У вас дороже, чем у конкурентов&quot;"}
          value={objection}
          onChange={(e) => setObjection(e.target.value)}
          disabled={streaming}
          rows={3}
          className="resize-none"
        />
      </div>

      {/* Поле контекста */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Контекст (какое масло предлагаем)</label>
        <Input
          placeholder="G-Energy Far East 5W-30, допуск SJ/GF-3"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          disabled={streaming}
        />
      </div>

      {/* Кнопка генерации */}
      <Button
        onClick={handleGenerate}
        disabled={streaming || !objection.trim()}
        className="w-full"
      >
        {streaming ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Генерация...
          </>
        ) : (
          <>
            <Sparkles className="mr-2 h-4 w-4" />
            Сгенерировать ответы
          </>
        )}
      </Button>

      {/* Ошибка */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="py-3 text-sm text-red-600">{error}</CardContent>
        </Card>
      )}

      {/* Зона стриминга — печатающийся текст */}
      {streaming && fullText && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Loader2 className="h-3 w-3 animate-spin" />
              ИИ думает...
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg bg-muted/50 p-4 min-h-[120px] max-h-[300px] overflow-y-auto">
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{fullText}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 3 карточки с вариантами ответов */}
      {!streaming && variants.length > 0 && (
        <div className="space-y-4">
          <p className="text-sm font-medium text-muted-foreground">
            Готово! Вот 3 варианта ответа:
          </p>
          <div className="space-y-4">
            {variants.map((v, i) => (
              <VariantCard key={i} variant={v} />
            ))}
          </div>
        </div>
      )}

      {/* Пустое состояние */}
      {!streaming && !fullText && variants.length === 0 && !error && (
        <div className="text-center py-8 space-y-2">
          <Bot className="h-10 w-10 mx-auto text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Введите возражение клиента и нажмите &quot;Сгенерировать ответы&quot;
          </p>
        </div>
      )}
    </div>
  );

  // =============================================================
  // Рендер: Dialog или Page режим
  // =============================================================

  if (isDialog) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Bot className="h-5 w-5" />
              AI-Суфлёр — Отработка возражений
            </DialogTitle>
            <DialogDescription>
              Помощник для менеджера: генерирует ответы на возражения клиентов
            </DialogDescription>
          </DialogHeader>
          {renderContent()}
          <DialogFooter>
            <Button variant="outline" onClick={handleReset}>
              Очистить
            </Button>
            <Button onClick={() => onOpenChange(false)}>Закрыть</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  // Page режим (полноэкранный)
  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Bot className="h-6 w-6" />
          AI-Суфлёр
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Генерируйте ответы на возражения клиентов в трёх стилях
        </p>
      </div>

      {renderContent()}
    </div>
  );
}
