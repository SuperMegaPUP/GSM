"use client";

import { Search, Upload, Users, Bot, ArrowRight } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DailyPlanWidget } from "@/components/DailyPlanWidget";
import { useSubscriptionStore } from "@/store/subscription-store";

// =============================================================
// Плитки быстрого доступа
// =============================================================

const quickLinks = [
  {
    href: "/dashboard/search",
    icon: Search,
    title: "Подбор масел",
    description: "Найдите масло по марке, модели и году авто",
    color: "from-blue-500 to-blue-600",
  },
  {
    href: "/dashboard/imports",
    icon: Upload,
    title: "Загрузка каталогов",
    description: "Загрузите Excel-каталог для пополнения базы",
    color: "from-emerald-500 to-emerald-600",
  },
  {
    href: "/dashboard/clients",
    icon: Users,
    title: "Клиенты",
    description: "Управление компаниями и пользователями",
    color: "from-violet-500 to-violet-600",
  },
  {
    href: "/dashboard/sales-copilot",
    icon: Bot,
    title: "AI-Суфлёр",
    description: "Отработка возражений клиентов с помощью AI",
    color: "from-amber-500 to-amber-600",
  },
];

const statusLabels: Record<string, { label: string; color: string }> = {
  ACTIVE: { label: "Активна", color: "text-emerald-600" },
  GRACE_PERIOD: { label: "Истекает", color: "text-amber-600" },
  SUSPENDED: { label: "Приостановлена", color: "text-red-600" },
  BLOCKED: { label: "Заблокирована", color: "text-red-700" },
};

export default function DashboardPage() {
  const subscription = useSubscriptionStore((s) => s.subscription);

  const statusInfo = subscription
    ? statusLabels[subscription.status] ?? { label: "—", color: "text-muted-foreground" }
    : { label: "—", color: "text-muted-foreground" };

  const showPlanWidget = subscription?.status === "ACTIVE" || subscription?.status === "GRACE_PERIOD";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Панель управления</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Добро пожаловать в систему подбора моторных масел
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {quickLinks.map((link) => (
          <Link key={link.href} href={link.href}>
            <Card className="group cursor-pointer transition-all hover:shadow-md">
              <CardHeader>
                <div
                  className={`mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br text-white ${link.color}`}
                >
                  <link.icon className="h-5 w-5" />
                </div>
                <CardTitle className="text-base">{link.title}</CardTitle>
                <CardDescription>{link.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="ghost" size="sm" className="group-hover:gap-2 transition-all px-0">
                  <span>Перейти</span>
                  <ArrowRight className="ml-1 h-3 w-3 transition-transform group-hover:translate-x-1" />
                </Button>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>

      {/* Daily Plan Widget */}
      {showPlanWidget && (
        <div className="max-w-lg">
          <DailyPlanWidget />
        </div>
      )}

      {/* Статистика */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Загружено каталогов
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">—</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Позиций в базе
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">—</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Статус подписки
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-bold ${statusInfo.color}`}>
              {statusInfo.label}
            </p>
            {subscription && subscription.days_left != null && (
              <p className="text-xs text-muted-foreground mt-1">
                {subscription.days_left} {subscription.days_left === 1 ? "день" : "дней"} осталось
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
