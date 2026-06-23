"use client";

import { Lock } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useSubscriptionStore } from "@/store/subscription-store";

export function SuspendedBanner() {
  const subscription = useSubscriptionStore((s) => s.subscription);

  if (!subscription || (subscription.status !== "SUSPENDED" && subscription.status !== "BLOCKED")) {
    return null;
  }

  return (
    <Alert variant="destructive" className="rounded-none border-x-0 border-t-0">
      <Lock className="h-4 w-4" />
      <AlertTitle>🔒 Доступ приостановлен</AlertTitle>
      <AlertDescription className="flex items-center justify-between gap-4">
        <span>
          Ваша подписка истекла. Оплатите для восстановления доступа ко всем функциям.
        </span>
        <Link href="/dashboard/billing">
          <Button size="sm" variant="default">Оплатить сейчас</Button>
        </Link>
      </AlertDescription>
    </Alert>
  );
}
