"use client";

import { useState } from "react";
import { CreditCard, Calendar, RefreshCw } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useSubscriptionStore } from "@/store/subscription-store";
import api from "@/lib/api";
import { toast } from "sonner";

const statusLabels: Record<string, { label: string; variant: "default" | "destructive" | "secondary" }> = {
  ACTIVE: { label: "Активна", variant: "default" },
  GRACE_PERIOD: { label: "Льготный период", variant: "secondary" },
  SUSPENDED: { label: "Приостановлена", variant: "destructive" },
  BLOCKED: { label: "Заблокирована", variant: "destructive" },
};

const planLabels: Record<string, string> = {
  BASIC: "Базовый",
  PRO: "Профессиональный",
  ENTERPRISE: "Enterprise",
};

export default function BillingPage() {
  const subscription = useSubscriptionStore((s) => s.subscription);
  const loading = useSubscriptionStore((s) => s.loading);
  const fetchSubscription = useSubscriptionStore((s) => s.fetchSubscription);
  const [activating, setActivating] = useState(false);

  const handleActivate = async (months: number) => {
    setActivating(true);
    try {
      await api.post("/billing/activate", { months });
      await fetchSubscription();
      toast.success(`Подписка продлена на ${months} ${months === 1 ? "месяц" : "месяца"}`);
    } catch {
      // Сообщение об ошибке уже нормализовано в axios interceptor
      toast.error("Ошибка при продлении подписки");
    } finally {
      setActivating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Биллинг</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Управление подпиской и оплатой
        </p>
      </div>

      {loading && !subscription ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : subscription ? (
        <>
          {/* Текущая подписка */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-muted-foreground" />
                <CardTitle>Текущая подписка</CardTitle>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-sm text-muted-foreground">Тариф</p>
                  <p className="text-lg font-semibold">
                    {planLabels[subscription.plan_type] ?? subscription.plan_type}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Статус</p>
                  <Badge variant={statusLabels[subscription.status]?.variant ?? "secondary"}>
                    {statusLabels[subscription.status]?.label ?? subscription.status}
                  </Badge>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Цена</p>
                  <p className="text-lg font-semibold">
                    {subscription.monthly_price} {subscription.currency}
                    <span className="text-sm font-normal text-muted-foreground">/мес</span>
                  </p>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  <span>
                    Действует до:{" "}
                    <strong className="text-foreground">
                      {new Date(subscription.end_date).toLocaleDateString("ru-RU")}
                    </strong>
                  </span>
                </div>
                {subscription.days_left != null && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <RefreshCw className="h-4 w-4" />
                    <span>
                      Осталось:{" "}
                      <strong className="text-foreground">
                        {subscription.days_left} {subscription.days_left === 1 ? "день" : "дней"}
                      </strong>
                    </span>
                  </div>
                )}
              </div>

              {/* Кнопки управления */}
              <div className="flex flex-wrap gap-3 pt-2">
                <Button
                  onClick={() => handleActivate(1)}
                  disabled={activating}
                >
                  {activating ? "Продление..." : "Продлить на месяц"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => handleActivate(3)}
                  disabled={activating}
                >
                  Продлить на 3 месяца
                </Button>
                <Button
                  variant="outline"
                  onClick={() => toast.info("Смена тарифа — в разработке")}
                >
                  Сменить тариф
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* История платежей (mock) */}
          <Card>
            <CardHeader>
              <CardTitle>История платежей</CardTitle>
              <CardDescription>Здесь будут отображаться ваши платежи</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Дата</TableHead>
                    <TableHead>Сумма</TableHead>
                    <TableHead>Статус</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-muted-foreground py-6">
                      История платежей пока пуста
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      ) : (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            Не удалось загрузить информацию о подписке
          </CardContent>
        </Card>
      )}
    </div>
  );
}
