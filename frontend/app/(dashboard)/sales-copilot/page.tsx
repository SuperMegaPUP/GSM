// =============================================================
// Страница AI-Суфлёр — полноэкранный режим Sales Copilot
// Доступна из сайдбара для работы с общими возражениями
// =============================================================

"use client";

import { SalesCopilot } from "@/components/SalesCopilot";

export default function SalesCopilotPage() {
  return <SalesCopilot open={true} onOpenChange={() => {}} variant="page" />;
}
