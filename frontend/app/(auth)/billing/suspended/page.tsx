"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Lock } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useSubscriptionStore } from "@/store/subscription-store";
import { useAuthStore } from "@/store/auth-store";

const plans = [
  {
    name: "BASIC",
    label: "Базовый",
    price: "0 ₽",
    features: ["Поиск масел", "База 50 000+ позиций", "10 импортов/мес"],
  },
  {
    name: "PRO",
    label: "Профессиональный",
    price: "4 990 ₽",
    features: ["Поиск масел", "База 200 000+ позиций", "Неограниченно импортов", "AI-Суфлёр", "Приоритетная поддержка"],
  },
  {
    name: "ENTERPRISE",
    label: "Enterprise",
    price: "Договорная",
    features: ["Всё из PRO", "Выделенный менеджер", "Интеграция с 1С", "API доступ", "Персональная настройка"],
  },
];

export default function SuspendedPage() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const subscription = useSubscriptionStore((s) => s.subscription);
  const fetchSubscription = useSubscriptionStore((s) => s.fetchSubscription);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    fetchSubscription();
  }, [isAuthenticated, router, fetchSubscription]);

  // Если подписка активна — редирект обратно в дашборд
  useEffect(() => {
    if (subscription?.is_active) {
      router.replace("/dashboard");
    }
  }, [subscription, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/20">
            <Lock className="h-8 w-8 text-red-600" />
          </div>
          <CardTitle className="text-2xl">Доступ приостановлен</CardTitle>
          <CardDescription className="text-base">
            Ваша подписка истекла. Оплатите для восстановления доступа ко всем функциям.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Таблица тарифов */}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-1/4">Тариф</TableHead>
                <TableHead className="w-1/4">Цена</TableHead>
                <TableHead className="w-2/4">Возможности</TableHead>
                <TableHead className="w-1/6"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {plans.map((plan) => (
                <TableRow key={plan.name}>
                  <TableCell className="font-medium">{plan.label}</TableCell>
                  <TableCell>{plan.price}</TableCell>
                  <TableCell>
                    <ul className="text-xs text-muted-foreground space-y-0.5">
                      {plan.features.map((f, i) => (
                        <li key={i} className="flex items-center gap-1">
                          <span className="text-emerald-500">✓</span> {f}
                        </li>
                      ))}
                    </ul>
                  </TableCell>
                  <TableCell>
                    <Button
                      size="sm"
                      onClick={() =>
                        plan.name === "BASIC"
                          ? router.push("/dashboard/billing")
                          : alert(`Тариф "${plan.label}" — оплата в разработке`)
                      }
                    >
                      Оплатить
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>

          <div className="text-center text-sm text-muted-foreground">
            <Link href="/login" className="underline hover:text-foreground">
              Войти под другим аккаунтом
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
