"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Search, Loader2, AlertCircle, Bot } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { SalesCopilot } from "@/components/SalesCopilot";
import api from "@/lib/api";

// =============================================================
// Типы данных (соответствуют backend/app/schemas/search_schemas.py)
// =============================================================

interface FluidSearchResult {
  fluid_id: string;
  canonical_name: string;
  brand: string | null;
  product_line: string | null;
  viscosity_sae: string | null;
  api_class: string | null;
  acea_class: string | null;
  oem_approvals: string[];
  fluid_type: string;
  volume_liters: number | null;
  volume_with_filter: number | null;
  is_oem_recommendation: boolean;
  confidence_score: number | null;
  oem_specification: string | null;
}

interface NodeGroupResult {
  node_type: string;
  node_label: string;
  recommendations: FluidSearchResult[];
}

interface SearchResponse {
  found_by: string;
  variant_id: string | null;
  brand: string;
  model: string;
  engine_code: string | null;
  engine_volume: number | null;
  year_start: number | null;
  year_end: number | null;
  groups: NodeGroupResult[];
}

// =============================================================
// Маппинг node_type на иконки и лейблы вкладок
// =============================================================

const NODE_TABS: Record<string, { icon: string; label: string }> = {
  ENGINE: { icon: "🛢️", label: "Двигатель" },
  MANUAL_TRANSMISSION: { icon: "⚙️", label: "МКПП" },
  AUTO_TRANSMISSION: { icon: "🔄", label: "АКПП" },
  CVT: { icon: "🔁", label: "Вариатор" },
  TRANSFER_CASE: { icon: "🔧", label: "Раздатка" },
  FRONT_DIFF: { icon: "🔩", label: "Передний мост" },
  REAR_DIFF: { icon: "🔩", label: "Задний мост" },
  STEERING: { icon: "💧", label: "ГУР" },
  BRAKE: { icon: "🛑", label: "Тормозная система" },
  COOLANT: { icon: "❄️", label: "Охлаждение" },
};

// =============================================================
// Компонент карточки масла
// =============================================================

function FluidCard({ fluid }: { fluid: FluidSearchResult }) {
  const [copilotOpen, setCopilotOpen] = useState(false);

  // Формируем контекст для ИИ из данных масла
  const contextText = [fluid.brand, fluid.product_line, fluid.viscosity_sae, fluid.api_class]
    .filter(Boolean)
    .join(", ");

  return (
    <>
      <Card className="group transition-all hover:shadow-md">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <CardTitle className="text-base leading-tight">
                {fluid.brand && fluid.product_line
                  ? `${fluid.brand} ${fluid.product_line}`
                  : fluid.canonical_name}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {fluid.canonical_name}
              </p>
            </div>
            <Badge
              variant={fluid.is_oem_recommendation ? "default" : "secondary"}
              className={
                fluid.is_oem_recommendation
                  ? "bg-emerald-500 hover:bg-emerald-600 shrink-0"
                  : "bg-amber-500 hover:bg-amber-600 text-white shrink-0"
              }
            >
              {fluid.is_oem_recommendation
                ? "🟢 OEM"
                : "🟡 Аналог"}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Характеристики */}
          <div className="grid grid-cols-2 gap-2 text-sm">
            {fluid.viscosity_sae && (
              <div className="rounded-md bg-muted/50 p-2">
                <p className="text-xs text-muted-foreground">Вязкость SAE</p>
                <p className="font-semibold">{fluid.viscosity_sae}</p>
              </div>
            )}
            {fluid.api_class && (
              <div className="rounded-md bg-muted/50 p-2">
                <p className="text-xs text-muted-foreground">Класс API</p>
                <p className="font-semibold">{fluid.api_class}</p>
              </div>
            )}
            {fluid.acea_class && (
              <div className="rounded-md bg-muted/50 p-2">
                <p className="text-xs text-muted-foreground">Класс ACEA</p>
                <p className="font-semibold">{fluid.acea_class}</p>
              </div>
            )}
            {fluid.volume_liters !== null && (
              <div className="rounded-md bg-muted/50 p-2">
                <p className="text-xs text-muted-foreground">Объём</p>
                <p className="font-semibold">
                  {fluid.volume_liters} л
                  {fluid.volume_with_filter && (
                    <span className="text-xs text-muted-foreground ml-1">
                      ({fluid.volume_with_filter} л с фильтром)
                    </span>
                  )}
                </p>
              </div>
            )}
          </div>

          {/* Допуски OEM */}
          {fluid.oem_approvals.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Допуски OEM:</p>
              <div className="flex flex-wrap gap-1">
                {fluid.oem_approvals.map((approval) => (
                  <Badge
                    key={approval}
                    variant="outline"
                    className="text-xs"
                  >
                    {approval}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Спецификация OEM */}
          {fluid.oem_specification && (
            <p className="text-xs text-muted-foreground">
              Спецификация: {fluid.oem_specification}
            </p>
          )}

          {/* Кнопка ИИ-эксперт */}
          <Button
            variant="outline"
            size="sm"
            className="w-full mt-2"
            onClick={() => setCopilotOpen(true)}
          >
            <Bot className="mr-2 h-4 w-4" />
            Спросить ИИ-эксперта
          </Button>
        </CardContent>
      </Card>

      {/* Sales Copilot виджет (Dialog) с контекстом масла */}
      <SalesCopilot
        open={copilotOpen}
        onOpenChange={setCopilotOpen}
        initialContext={contextText}
        variant="dialog"
      />
    </>
  );
}

// =============================================================
// Компонент формы поиска
// =============================================================

function SearchForm({
  onSearch,
  loading,
}: {
  onSearch: (params: Record<string, string | number>) => void;
  loading: boolean;
}) {
  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [year, setYear] = useState("");
  const [engineCode, setEngineCode] = useState("");
  const [engineVolume, setEngineVolume] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const params: Record<string, string | number> = {};
    if (brand.trim()) params.brand = brand.trim();
    if (model.trim()) params.model = model.trim();
    if (year.trim()) params.year = parseInt(year.trim(), 10);
    if (engineCode.trim()) params.engine_code = engineCode.trim();
    if (engineVolume.trim()) params.engine_volume = parseFloat(engineVolume.trim());

    // Валидация: хотя бы одно поле
    if (Object.keys(params).length === 0) {
      toast.error("Укажите хотя бы один параметр поиска (марка, модель, год или код двигателя)");
      return;
    }

    onSearch(params);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Search className="h-5 w-5" />
          Подбор масел
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {/* Марка */}
            <div className="space-y-2">
              <Label htmlFor="brand">Марка</Label>
              <Input
                id="brand"
                placeholder="Toyota"
                value={brand}
                onChange={(e) => setBrand(e.target.value)}
              />
            </div>

            {/* Модель */}
            <div className="space-y-2">
              <Label htmlFor="model">Модель</Label>
              <Input
                id="model"
                placeholder="Camry"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
            </div>

            {/* Год */}
            <div className="space-y-2">
              <Label htmlFor="year">Год выпуска</Label>
              <Input
                id="year"
                type="number"
                placeholder="2020"
                min={1960}
                max={2030}
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </div>

            {/* Код двигателя */}
            <div className="space-y-2">
              <Label htmlFor="engine_code">Код двигателя</Label>
              <Input
                id="engine_code"
                placeholder="2AR-FE"
                value={engineCode}
                onChange={(e) => setEngineCode(e.target.value)}
              />
            </div>

            {/* Объём двигателя */}
            <div className="space-y-2">
              <Label htmlFor="engine_volume">Объём двигателя (л)</Label>
              <Input
                id="engine_volume"
                type="number"
                step="0.1"
                placeholder="2.5"
                value={engineVolume}
                onChange={(e) => setEngineVolume(e.target.value)}
              />
            </div>
          </div>

          <Button type="submit" className="w-full sm:w-auto" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Поиск...
              </>
            ) : (
              <>
                <Search className="mr-2 h-4 w-4" />
                Подобрать масла
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

// =============================================================
// Компонент пустого состояния
// =============================================================

function EmptyState() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center py-16 space-y-4">
        <AlertCircle className="h-12 w-12 text-muted-foreground" />
        <div className="text-center space-y-2">
          <p className="text-lg font-semibold">Точных рекомендаций не найдено</p>
          <p className="text-sm text-muted-foreground max-w-md">
            Попробуйте изменить параметры поиска или воспользуйтесь ИИ-поиском
            аналогов. Укажите марку и модель автомобиля для лучших результатов.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

// =============================================================
// Компонент скелетона загрузки
// =============================================================

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-10 w-64" />
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-6 w-48" />
            </CardHeader>
            <CardContent className="space-y-3">
              {[1, 2].map((j) => (
                <Card key={j}>
                  <CardHeader>
                    <Skeleton className="h-5 w-56" />
                    <Skeleton className="h-4 w-32 mt-1" />
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="grid grid-cols-2 gap-2">
                      <Skeleton className="h-12 w-full" />
                      <Skeleton className="h-12 w-full" />
                    </div>
                    <Skeleton className="h-8 w-full" />
                  </CardContent>
                </Card>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// =============================================================
// Основной компонент страницы поиска
// =============================================================

export default function SearchPage() {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (params: Record<string, string | number>) => {
    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const response = await api.post<SearchResponse>("/search/oils", params);
      setResults(response.data);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } }; message?: string };
      const message =
        axiosErr.response?.data?.detail ||
        axiosErr.message ||
        "Ошибка при поиске масел";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Подбор масел</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Найдите рекомендованные масла и жидкости для вашего автомобиля
        </p>
      </div>

      {/* Форма поиска */}
      <SearchForm onSearch={handleSearch} loading={loading} />

      {/* Ошибка */}
      {error && (
        <Card>
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500 shrink-0" />
            <p className="text-sm text-red-600">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Результаты */}
      {loading && <LoadingSkeleton />}

      {!loading && results && results.groups.length > 0 && (
        <div className="space-y-4">
          {/* Информация о найденном варианте */}
          <Card>
            <CardContent className="py-4">
              <div className="flex flex-wrap items-center gap-4 text-sm">
                <span className="font-semibold">
                  {results.brand} {results.model}
                </span>
                {results.engine_code && (
                  <Badge variant="outline">{results.engine_code}</Badge>
                )}
                {results.engine_volume && (
                  <Badge variant="outline">{results.engine_volume} л</Badge>
                )}
                {results.year_start && results.year_end && (
                  <Badge variant="outline">
                    {results.year_start}–{results.year_end}
                  </Badge>
                )}
                <Badge
                  variant="outline"
                  className="ml-auto bg-blue-50 text-blue-700 border-blue-200"
                >
                  Найдено: {results.found_by === "exact_sql" ? "🟢 Точное совпадение" : "🟡 Семантический поиск"}
                </Badge>
              </div>
            </CardContent>
          </Card>

          {/* Вкладки по узлам */}
          <Tabs defaultValue={results.groups[0]?.node_type || ""}>
            <TabsList className="flex flex-wrap gap-2">
              {results.groups.map((group) => {
                const tabInfo = NODE_TABS[group.node_type] || {
                  icon: "🔧",
                  label: group.node_type,
                };
                return (
                  <TabsTrigger
                    key={group.node_type}
                    value={group.node_type}
                    className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground"
                  >
                    {tabInfo.icon} {tabInfo.label} ({group.recommendations.length})
                  </TabsTrigger>
                );
              })}
            </TabsList>

            {results.groups.map((group) => (
              <TabsContent key={group.node_type} value={group.node_type}>
                <div className="space-y-4 mt-4">
                  <p className="text-sm text-muted-foreground">
                    {group.node_label}: найдено {group.recommendations.length}{" "}
                    {group.recommendations.length === 1
                      ? "рекомендация"
                      : group.recommendations.length < 5
                        ? "рекомендации"
                        : "рекомендаций"}
                  </p>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {group.recommendations.map((fluid) => (
                      <FluidCard key={fluid.fluid_id} fluid={fluid} />
                    ))}
                  </div>
                </div>
              </TabsContent>
            ))}
          </Tabs>
        </div>
      )}

      {/* Пустое состояние */}
      {!loading && results && results.groups.length === 0 && <EmptyState />}
    </div>
  );
}
