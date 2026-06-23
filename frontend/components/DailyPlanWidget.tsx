"use client";

import { useState } from "react";
import { RefreshCw } from "lucide-react";

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
import { useSubscriptionStore } from "@/store/subscription-store";
import api from "@/lib/api";
import type { DailyPlanData } from "@/store/subscription-store";
import { toast } from "sonner";

const severityToVariant: Record<string, "destructive" | "default" | "secondary"> = {
  high: "destructive",
  medium: "default",
  low: "secondary",
};

const severityToLabel: Record<string, string> = {
  high: "Высокий",
  medium: "Средний",
  low: "Низкий",
};

export function DailyPlanWidget() {
  const dailyPlan = useSubscriptionStore((s) => s.dailyPlan);
  const loading = useSubscriptionStore((s) => s.loading);
  const setPlan = useSubscriptionStore((s) => s.setDailyPlan);
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const response = await api.get<DailyPlanData>("/analytics/daily-plan", {
        params: { force: true },
      });
      setPlan(response.data);
      toast.success("План действий обновлён");
    } catch {
      toast.error("Не удалось обновить план");
    } finally {
      setRefreshing(false);
    }
  };

  if (loading && !dailyPlan) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>📋 План действий на сегодня</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const items = dailyPlan?.items ?? [];

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between space-y-0">
        <div>
          <CardTitle>📋 План действий на сегодня</CardTitle>
          <CardDescription>
            Рекомендации на основе анализа данных
          </CardDescription>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={handleRefresh}
          disabled={refreshing}
          title="Обновить план"
        >
          <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
        </Button>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">
            На сегодня задач нет 🎉
          </p>
        ) : (
          <ul className="space-y-3">
            {items.map((item, index) => (
              <li key={index} className="flex items-start gap-3 text-sm">
                <Badge
                  variant={severityToVariant[item.severity] ?? "secondary"}
                  className="shrink-0 mt-0.5"
                >
                  {severityToLabel[item.severity] ?? item.severity}
                </Badge>
                <span className="text-foreground">{item.message}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
