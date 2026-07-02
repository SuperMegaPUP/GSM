"use client";

import { useState, useEffect, useRef } from "react";
import { toast } from "sonner";
import { Search, Loader2, AlertCircle, Bot } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

import { FluidCard, type RecommendationType } from "@/components/ui/gsm/FluidCard";
import { NODE_CONFIG, NodeIcon, type NodeType } from "@/components/ui/gsm/nodeTypes";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { SalesCopilot } from "@/components/SalesCopilot";

import api, { getBrands, getModels, type CarBrandRead, type CarModelRead } from "@/lib/api";
import {
  ComboboxRoot,
  ComboboxControl,
  ComboboxInput,
  ComboboxPopup,
  ComboboxList,
  ComboboxItem,
  ComboboxEmpty,
} from "@/components/ui/combobox";

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
  recommendation_rank: number;
  applicability_conditions: Record<string, unknown>;
  fluid_name_override: string | null;
}

interface NodeGroupResult {
  node_type: string;
  node_label: string;
  recommendations: FluidSearchResult[];
}

interface EngineVariantInfo {
  engine_code: string;
  engine_volume: number | null;
}

interface ModelSearchInfo {
  id: string;
  name: string;
  engine_code: string | null;
  engine_volume: number | null;
  year_start: number | null;
  year_end: number | null;
  variants_count: number;
  engine_volumes: number[];
  engine_variants: EngineVariantInfo[];
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
  models: ModelSearchInfo[];
}

// =============================================================
// Маппинг node_type на иконки и лейблы вкладок
// =============================================================



// =============================================================
// Компонент карточки масла
// =============================================================

const RANK_CONFIG: Record<number, { label: string; badgeClass: string }> = {
  1: { label: 'Рекомендуется', badgeClass: 'badge-oem' },
  2: { label: 'Альтернатива 1', badgeClass: 'badge-approval' },
  3: { label: 'Альтернатива 2', badgeClass: 'badge-alternative' },
};

function RankBadge({ rank }: { rank: number }) {
  const cfg = RANK_CONFIG[rank];
  if (cfg) {
    return <span className={`badge ${cfg.badgeClass}`}>{cfg.label}</span>;
  }
  return <span className="badge badge-alternative">Сноска ({rank})</span>;
}

function FluidCardWrapper({ fluid }: { fluid: FluidSearchResult }) {
  const [copilotOpen, setCopilotOpen] = useState(false);

  const contextText = [fluid.brand, fluid.product_line, fluid.viscosity_sae, fluid.api_class]
    .filter(Boolean)
    .join(", ");

  const recType: RecommendationType = fluid.is_oem_recommendation
    ? 'oem'
    : fluid.oem_approvals.length > 0
      ? 'approval'
      : 'alternative';

  const specs: { label: string; kind?: 'sae' | 'api' | 'default' }[] = [];
  if (fluid.viscosity_sae) specs.push({ label: fluid.viscosity_sae, kind: 'sae' });
  if (fluid.api_class) specs.push({ label: fluid.api_class, kind: 'api' });
  if (fluid.acea_class) specs.push({ label: fluid.acea_class });

  return (
    <>
      <FluidCard
        brand={fluid.brand || ''}
        name={fluid.product_line || fluid.canonical_name}
        type={recType}
        specs={specs}
        volume={fluid.volume_liters !== null ? `${fluid.volume_liters} L` : undefined}
        volumeWithFilter={fluid.volume_with_filter !== null ? `${fluid.volume_with_filter} L` : undefined}
        extra={
          <div className="space-y-2">
            <RankBadge rank={fluid.recommendation_rank} />
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setCopilotOpen(true)}
            >
              <Bot className="mr-2 h-4 w-4" />
              Спросить ИИ-эксперта
            </Button>
          </div>
        }
      />

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
  onReset,
  loading,
}: {
  onSearch: (params: Record<string, string | number>) => void;
  onReset?: () => void;
  loading: boolean;
}) {
  const [brand, setBrand] = useState("");
  const [brandId, setBrandId] = useState<string | null>(null);
  const [model, setModel] = useState("");
  const [year, setYear] = useState("");
  const [engineCode, setEngineCode] = useState("");
  const [engineVolume, setEngineVolume] = useState("");

  // Данные для автоподбора
  const [brandItems, setBrandItems] = useState<CarBrandRead[]>([]);
  const [modelItems, setModelItems] = useState<CarModelRead[]>([]);
  const brandTimer = useRef<NodeJS.Timeout>();
  const modelTimer = useRef<NodeJS.Timeout>();

  // Загружаем марки при монтировании
  useEffect(() => {
    getBrands(undefined, 200).then((res) => setBrandItems(res.items));
  }, []);

  // Загружаем модели при выборе марки
  useEffect(() => {
    if (brandId) {
      getModels(brandId, undefined, 200).then((res) => setModelItems(res.items));
      setModel("");
    } else {
      setModelItems([]);
    }
  }, [brandId]);

  const handleBrandValueChange = (val: string | null) => {
    const v = val ?? "";
    setBrand(v);
    const found = brandItems.find((b) => b.name_ru === v);
    setBrandId(found?.id ?? null);
  };

  const handleBrandSearch = (val: string) => {
    setBrand(val);
    clearTimeout(brandTimer.current);
    brandTimer.current = setTimeout(() => {
      getBrands(val || undefined, 200).then((res) => setBrandItems(res.items));
    }, 300);
  };

  const handleModelSearch = (val: string) => {
    setModel(val);
    if (!brandId) return;
    clearTimeout(modelTimer.current);
    modelTimer.current = setTimeout(() => {
      getModels(brandId, val || undefined, 200).then((res) => setModelItems(res.items));
    }, 300);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const params: Record<string, string | number> = {};
    if (brand.trim()) params.brand = brand.trim();
    if (model.trim()) params.model = model.trim();
    if (year.trim()) params.year = parseInt(year.trim(), 10);
    if (engineCode.trim()) params.engine_code = engineCode.trim();
    if (engineVolume.trim()) params.engine_volume = parseFloat(engineVolume.trim());

    if (Object.keys(params).length === 0) {
      toast.error("Укажите хотя бы один параметр поиска (марка, модель, год или код двигателя)");
      return;
    }

    onSearch(params);
  };

  const handleReset = () => {
    setBrand("");
    setBrandId(null);
    setModel("");
    setYear("");
    setEngineCode("");
    setEngineVolume("");
    onReset?.();
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
              <Label htmlFor="brand-combobox">Марка</Label>
              <ComboboxRoot value={brand} onValueChange={handleBrandValueChange} onInputValueChange={handleBrandSearch}>
                <ComboboxControl id="brand-combobox">
                  <ComboboxInput placeholder="Выберите марку" />
                </ComboboxControl>
                <ComboboxPopup>
                  <ComboboxList>
                    {brandItems.map((b) => (
                      <ComboboxItem key={b.id} value={b.name_ru}>
                        {b.name_ru}
                      </ComboboxItem>
                    ))}
                  </ComboboxList>
                  <ComboboxEmpty>Марка не найдена</ComboboxEmpty>
                </ComboboxPopup>
              </ComboboxRoot>
            </div>

            {/* Модель */}
            <div className="space-y-2">
              <Label htmlFor="model-combobox">Модель</Label>
              <ComboboxRoot
                value={model}
                onValueChange={(val) => setModel(val ?? "")}
                onInputValueChange={handleModelSearch}
              >
                <ComboboxControl id="model-combobox">
                  <ComboboxInput placeholder={brand ? "Выберите модель" : "Сначала выберите марку"} />
                </ComboboxControl>
                <ComboboxPopup>
                  <ComboboxList>
                    {modelItems.map((m) => (
                      <ComboboxItem key={m.id} value={m.name}>
                        {m.name}
                        {m.generation && <span className="text-xs text-muted-foreground">({m.generation})</span>}
                        {m.year_start && m.year_end && (
                          <span className="text-xs text-muted-foreground ml-auto">{m.year_start}-{m.year_end}</span>
                        )}
                      </ComboboxItem>
                    ))}
                  </ComboboxList>
                  <ComboboxEmpty>Модель не найдена</ComboboxEmpty>
                </ComboboxPopup>
              </ComboboxRoot>
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

          <div className="flex gap-2">
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
            <Button type="button" variant="outline" onClick={handleReset} disabled={loading}>
              Сбросить
            </Button>
          </div>
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
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [activeNodeTab, setActiveNodeTab] = useState<string>("ENGINE");
  const [lastSearchParams, setLastSearchParams] = useState<Record<string, string | number>>({});

  const handleReset = () => {
    setResults(null);
    setError(null);
    setSelectedModel(null);
    setActiveNodeTab("ENGINE");
    setLastSearchParams({});
  };

  const handleEngineVolumeSelect = (volume: number | null) => {
    const params = { ...lastSearchParams };
    if (volume !== null) {
      params.engine_volume = volume;
    } else {
      delete params.engine_volume;
    }
    handleSearch(params);
  };

  const clearEngineVolume = () => handleEngineVolumeSelect(null);

  const handleEngineCodeSelect = (code: string | null) => {
    const params = { ...lastSearchParams };
    if (code !== null) {
      params.engine_code = code;
    } else {
      delete params.engine_code;
    }
    handleSearch(params);
  };

  const clearEngineCode = () => handleEngineCodeSelect(null);

  const activeEngineCode = lastSearchParams.engine_code as string | undefined;

  const handleSearch = async (params: Record<string, string | number>) => {
    setLoading(true);
    setError(null);
    setResults(null);
    setLastSearchParams(params);

    try {
      const response = await api.post<SearchResponse>("/search/oils", params);
      setResults(response.data);
} catch (err: unknown) {
      const axiosErr = err as Error & { response?: { data?: Record<string, unknown> } };
      const errRecord = axiosErr as unknown as Record<string, unknown>;
      const detail =
        ((axiosErr.response?.data ?? {}) as Record<string, unknown>).detail ??
        ((axiosErr.response?.data ?? {}) as Record<string, unknown>).error ??
        errRecord.detail ??
        errRecord.error;
      let message: string;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((d: unknown) => {
            const errObj = d as Record<string, unknown>;
            return String(errObj.msg || errObj.detail || d);
          })
          .join("; ");
      } else if (detail && typeof detail === "object") {
        const detailObj = detail as Record<string, unknown>;
        message = String(detailObj.msg || detailObj.detail || JSON.stringify(detail));
      } else {
        message = axiosErr.message || "Ошибка при поиске масел";
      }
      // Гарантируем, что message — строка (не объект!)
      if (typeof message !== "string") {
        message = String(message);
      }
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
      <SearchForm onSearch={handleSearch} onReset={handleReset} loading={loading} />

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
                {results.models.length > 1 ? (
                  <>
                    <span className="font-semibold">{results.brand}</span>
                    <Badge variant="outline" className="bg-purple-50 text-purple-700 border-purple-200">
                      🚗 {results.models.length} моделей
                    </Badge>
                  </>
                ) : (
                  <>
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
                  </>
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

          {/* Вкладки/селектор по моделям (когда найдено несколько) */}
          {results.models.length > 1 && (
            <Card>
              <CardContent className="py-4 space-y-3">
                <p className="text-sm font-medium">Найдено {results.models.length} моделей {results.brand}:</p>
                
                {results.models.length <= 10 ? (
                  <div className="flex flex-wrap gap-2">
                    {results.models.map((m) => (
                      <button
                        key={`model-${m.id}`}
                        onClick={() => {
                          setSelectedModel(m.name);
                          setActiveNodeTab(results.groups[0]?.node_type || "ENGINE");
                        }}
                        className={`px-3 py-1.5 text-xs font-medium rounded-md border transition-colors ${
                          (selectedModel || results.models[0]?.name) === m.name
                            ? "bg-primary text-primary-foreground border-primary"
                            : "bg-background text-foreground border-border hover:bg-muted"
                        }`}
                      >
                        {m.name}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="space-y-2">
                    <Select value={selectedModel || results.models[0]?.name} onValueChange={(val) => {
                      setSelectedModel(val);
                      setActiveNodeTab(results.groups[0]?.node_type || "ENGINE");
                    }}>
                      <SelectTrigger className="w-full sm:w-80">
                        <SelectValue placeholder="Выберите модель" />
                      </SelectTrigger>
                      <SelectContent>
                        {results.models.map((m) => (
                          <SelectItem key={`select-${m.id}`} value={m.name}>
                            {m.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Показаны все {results.models.length} моделей. Выберите конкретную для точного подбора.
                    </p>
                  </div>
                )}

                {/* Фильтр по объёму двигателя для выбранной модели */}
                {(() => {
                  const currentModel = results.models.find(
                    (m) => m.name === (selectedModel || results.models[0]?.name)
                  );
                  if (!currentModel || (currentModel.engine_volumes.length === 0 && currentModel.engine_variants.length === 0)) return null;
                  const activeVolume = lastSearchParams.engine_volume as number | undefined;
                  return (
                    <div className="space-y-2 pt-1">
                      {currentModel.engine_volumes.length > 0 && (
                        <div className="space-y-1.5">
                          <p className="text-xs text-muted-foreground">Объём двигателя:</p>
                          <div className="flex flex-wrap gap-1.5">
                            {currentModel.engine_volumes.map((v) => (
                              <button
                                key={`vol-${v}`}
                                onClick={() => handleEngineVolumeSelect(v)}
                                className={`px-2.5 py-1 text-xs font-medium rounded-md border transition-colors ${
                                  activeVolume === v
                                    ? "bg-primary text-primary-foreground border-primary"
                                    : "bg-background text-foreground border-border hover:bg-muted"
                                }`}
                              >
                                {v} л
                              </button>
                            ))}
                            {activeVolume !== undefined && (
                              <button
                                onClick={clearEngineVolume}
                                className="px-2.5 py-1 text-xs font-medium rounded-md border border-border bg-background text-muted-foreground hover:bg-muted"
                              >
                                ✕
                              </button>
                            )}
                          </div>
                        </div>
                      )}

                      {currentModel.engine_variants.length > 0 && (
                        <div className="space-y-1.5">
                          <p className="text-xs text-muted-foreground">Мотор:</p>
                          <div className="flex flex-wrap gap-1.5">
                            {currentModel.engine_variants.map((ev) => (
                              <button
                                key={`ev-${ev.engine_code}`}
                                onClick={() => handleEngineCodeSelect(
                                  activeEngineCode === ev.engine_code ? null : ev.engine_code
                                )}
                                className={`font-mono px-2.5 py-1 text-xs font-medium rounded-md border transition-colors ${
                                  activeEngineCode === ev.engine_code
                                    ? "bg-primary text-primary-foreground border-primary"
                                    : "bg-background text-foreground border-border hover:bg-muted"
                                }`}
                              >
                                {ev.engine_code}
                                {ev.engine_volume !== null && (
                                  <span className="ml-1 opacity-70">({ev.engine_volume} л)</span>
                                )}
                              </button>
                            ))}
                            {activeEngineCode !== undefined && (
                              <button
                                onClick={clearEngineCode}
                                className="px-2.5 py-1 text-xs font-medium rounded-md border border-border bg-background text-muted-foreground hover:bg-muted"
                              >
                                ✕
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </CardContent>
            </Card>
          )}

          {/* Вкладки по узлам (компактные, горизонтальные) */}
          <div className="space-y-4">
            <div className="flex flex-wrap gap-1.5">
              {results.groups.map((group) => {
                const nodeType = group.node_type as NodeType;
                const cfg = NODE_CONFIG[nodeType];
                const pillClass = cfg?.pillClass || 'node-pill-engine';
                return (
                  <button
                    key={`node-${group.node_type}`}
                    onClick={() => setActiveNodeTab(group.node_type)}
                    className={`node-pill ${pillClass} ${
                      activeNodeTab === group.node_type ? 'ring-2 ring-[var(--foreground)]' : 'opacity-70'
                    }`}
                    aria-pressed={activeNodeTab === group.node_type}
                  >
                    {cfg && <NodeIcon type={nodeType} size={12} />}
                    <span>{cfg?.shortLabel || group.node_type}</span>
                    <span className="tabular-nums ml-0.5">({group.recommendations.length})</span>
                  </button>
                );
              })}
            </div>

            {results.groups.map((group) =>
              activeNodeTab !== group.node_type ? null : (
                <div key={`content-${group.node_type}`} className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    {group.node_label}: найдено {group.recommendations.length}{" "}
                    {group.recommendations.length === 1
                      ? "рекомендация"
                      : group.recommendations.length < 5
                        ? "рекомендации"
                        : "рекомендаций"}
                  </p>
                  <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                    {[...group.recommendations]
                      .sort((a, b) => a.recommendation_rank - b.recommendation_rank)
                      .map((fluid) => (
                        <FluidCardWrapper key={fluid.fluid_id} fluid={fluid} />
                      ))}
                  </div>
                </div>
              )
            )}
          </div>
        </div>
      )}

      {/* Пустое состояние */}
      {!loading && results && results.groups.length === 0 && <EmptyState />}
    </div>
  );
}
