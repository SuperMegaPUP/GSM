"use client";

import { Search, Upload, Users, Bot, ArrowRight } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// =============================================================
// Плитки быстрого доступа
// =============================================================

const quickLinks = [
  {
    href: "/dashboard",
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

export default function DashboardPage() {
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
            <p className="text-2xl font-bold text-emerald-600">Активна</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
