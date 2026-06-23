"use client";

import { SalesCopilotChat } from "@/components/SalesCopilotChat";
import { useAuthStore } from "@/store/auth-store";

export default function SalesCopilotPage() {
  const user = useAuthStore((s) => s.user);

  if (!user) return <div className="p-6">Загрузка...</div>;

  return (
    <div className="p-0">
      <SalesCopilotChat
        apiUrl="/api/v1/sales/handle-objection"
        feedbackUrl="/api/v1/sales/objection-cases"
        user={{
          id: user.id,
          name: user.full_name,
          initials: (user.full_name || "??")
            .split(" ")
            .map((n: string) => n[0])
            .join("")
            .toUpperCase()
            .slice(0, 2),
          company_id: user.company_id,
        }}
      />
    </div>
  );
}
