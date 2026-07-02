"use client";

import { useCallback, useEffect, useState } from "react";
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Lightbulb,
  Loader2,
  RefreshCw,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import api from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────

interface ActionItem {
  type: string;
  severity: string;
  message: string;
}

interface DailyPlan {
  items: ActionItem[];
}

interface TrendPoint {
  date: string;
  value: Record<string, unknown>;
}

interface Trends {
  objections_total: TrendPoint[];
  objections_by_category: TrendPoint[];
  case_stats: TrendPoint[];
}

interface Insight {
  type: string;
  severity: string;
  message: string;
}

// ─── Helpers ───────────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  high: "bg-red-100 text-red-700 border-red-200",
  warning: "bg-amber-100 text-amber-700 border-amber-200",
  info: "bg-blue-100 text-blue-700 border-blue-200",
};

const SEVERITY_ICONS: Record<string, React.ReactNode> = {
  high: <AlertTriangle className="h-4 w-4 text-red-500" />,
  warning: <AlertTriangle className="h-4 w-4 text-amber-500" />,
  info: <Lightbulb className="h-4 w-4 text-blue-500" />,
};

function severityBadge(severity: string) {
  const color = SEVERITY_COLORS[severity] || SEVERITY_COLORS.info;
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium ${color}`}>
      {SEVERITY_ICONS[severity]}
      {severity === "high" ? "Высокий" : severity === "warning" ? "Внимание" : "Инфо"}
    </span>
  );
}

// ─── Page ──────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [plan, setPlan] = useState<DailyPlan | null>(null);
  const [trends, setTrends] = useState<Trends | null>(null);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [planRes, trendsRes, insightsRes] = await Promise.all([
        api.get("/analytics/daily-plan"),
        api.get("/analytics/trends?days=30"),
        api.get("/analytics/insights"),
      ]);
      setPlan(planRes.data);
      setTrends(trendsRes.data);
      setInsights(insightsRes.data.insights || []);
    } catch (e) {
      console.error("Failed to load analytics:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Computed stats
  const latestStats = trends?.case_stats?.[trends.case_stats.length - 1]?.value || {};
  const latestTotal = trends?.objections_total?.[trends.objections_total.length - 1]?.value || {};

  if (loading) {
    return (
      <div className="flex h-60 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Аналитика</h1>
          <p className="text-sm text-muted-foreground">
            Статистика использования, тренды возражений и рекомендации
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchAll}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Обновить
        </Button>
      </div>

      {/* KPI cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Всего кейсов
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {String(latestStats.total_cases ?? "—")}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Использовано
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {String(latestStats.total_used ?? "—")}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Success Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {latestStats.success_rate != null
                ? `${(Number(latestStats.success_rate) * 100).toFixed(0)}%`
                : "—"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Возражений сегодня
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">
              {String((latestTotal as { count?: number }).count ?? "—")}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main content */}
      <div className="grid gap-6 lg:grid-cols-[1fr_400px]">
        {/* Left: Trends + Insights */}
        <div className="space-y-6">
          {/* Trends chart placeholder */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-4 w-4" />
                Тренды (30 дней)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {trends && trends.objections_total.length > 0 ? (
                <div className="space-y-1">
                  {trends.objections_total.map((p) => (
                    <div
                      key={p.date}
                      className="flex items-center justify-between rounded-md bg-muted/30 px-3 py-2 text-sm"
                    >
                      <span className="text-muted-foreground">{p.date}</span>
                      <span className="font-medium">
                        {(p.value as { count?: number }).count ?? 0} возражений
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Нет данных за период. Данные появятся после первого использования Sales Copilot.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Case stats card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <BarChart3 className="h-4 w-4" />
                Статистика кейсов
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold text-green-600">
                    {String(latestStats.total_won ?? 0)}
                  </div>
                  <div className="text-xs text-muted-foreground">Успешно</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-600">
                    {String(latestStats.total_lost ?? 0)}
                  </div>
                  <div className="text-xs text-muted-foreground">Неудачно</div>
                </div>
                <div>
                  <div className="text-2xl font-bold">
                    {String(latestStats.total_cases ?? 0)}
                  </div>
                  <div className="text-xs text-muted-foreground">Всего</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right: Plan + Insights */}
        <div className="space-y-6">
          {/* Daily plan */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <CheckCircle2 className="h-4 w-4" />
                План действий на сегодня
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {plan && plan.items.length > 0 ? (
                plan.items.map((item, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 rounded-md border p-3 text-sm"
                  >
                    {severityBadge(item.severity)}
                    <div className="flex-1">{item.message}</div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">
                  План пуст. Все показатели в норме.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Insights */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Lightbulb className="h-4 w-4" />
                Инсайты
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {insights.length > 0 ? (
                insights.map((ins, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 rounded-md border p-3 text-sm"
                  >
                    {severityBadge(ins.severity)}
                    <div className="flex-1">{ins.message}</div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">
                  Инсайтов пока нет. Накопите больше данных.
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
