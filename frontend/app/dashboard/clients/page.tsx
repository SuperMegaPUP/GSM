"use client";

import { Users, Plus, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function ClientsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Клиенты</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Управление компаниями и пользователями
          </p>
        </div>
        <Button disabled>
          <Plus className="mr-2 h-4 w-4" />
          Добавить клиента
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Поиск по компании или email..." className="pl-9" disabled />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Users className="h-4 w-4 text-muted-foreground" />
            Список клиентов
          </CardTitle>
          <CardDescription>
            Здесь будет отображаться список всех компаний с возможностью
            управления пользователями, подписками и ролями.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Users className="h-12 w-12 text-muted-foreground/40 mb-4" />
            <p className="text-sm font-medium">Модуль в разработке</p>
            <p className="text-xs text-muted-foreground mt-1">
              Таблица клиентов с фильтрацией, сортировкой и управлением появится в ближайшее время
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
