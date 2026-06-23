"use client";

import { AlertTriangle } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useSubscriptionStore } from "@/store/subscription-store";

export function GracePeriodBanner() {
  const subscription = useSubscriptionStore((s) => s.subscription);

  if (!subscription || subscription.status !== "GRACE_PERIOD") {
    return null;
  }

  const daysLeft = subscription.days_left ?? 0;

  return (
    <Alert variant="warning" className="rounded-none border-x-0 border-t-0">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>⚠️ Подписка истекает</AlertTitle>
      <AlertDescription className="flex items-center justify-between gap-4">
        <span>
          Ваша подписка истекает через <strong>{daysLeft}</strong>{" "}
          {daysLeft === 1 ? "день" : daysLeft < 5 ? "дня" : "дней"}.
          Оплатите для продолжения работы.
        </span>
        <Link href="/dashboard/billing">
          <Button size="sm" variant="default">Оплатить</Button>
        </Link>
      </AlertDescription>
    </Alert>
  );
}
