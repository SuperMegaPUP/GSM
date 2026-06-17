"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import {
  Upload,
  FileSpreadsheet,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Clock,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import api from "@/lib/api";

// =============================================================
// Типы данных
// =============================================================

interface ImportBatch {
  id: string;
  filename: string;
  status: string;
  total_rows: number;
  new_rows: number;
  duplicates: number;
  errors: number;
  created_at: string;
  review_notes?: string;
}

type ImportStatus = "pending" | "processing" | "review" | "completed" | "failed";

const STATUS_LABELS: Record<ImportStatus, string> = {
  pending: "В очереди",
  processing: "Обработка...",
  review: "На проверке",
  completed: "Готово",
  failed: "Ошибка",
};

const STATUS_COLORS: Record<ImportStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800 border-yellow-300",
  processing: "bg-blue-100 text-blue-800 border-blue-300",
  review: "bg-purple-100 text-purple-800 border-purple-300",
  completed: "bg-emerald-100 text-emerald-800 border-emerald-300",
  failed: "bg-red-100 text-red-800 border-red-300",
};

// =============================================================
// Моковые данные для истории (пока нет эндпоинта списка)
// =============================================================

const MOCK_HISTORY: ImportBatch[] = [
  {
    id: "mock-1",
    filename: "katalog_gsm_2024.xlsx",
    status: "completed",
    total_rows: 11167,
    new_rows: 9800,
    duplicates: 1200,
    errors: 167,
    created_at: "2024-06-15T10:30:00Z",
  },
  {
    id: "mock-2",
    filename: "catalog_honda.xlsx",
    status: "failed",
    total_rows: 5000,
    new_rows: 0,
    duplicates: 0,
    errors: 5000,
    created_at: "2024-06-14T14:20:00Z",
    review_notes: "Ошибка парсинга листа 3",
  },
];

// =============================================================
// Компонент прогресс-бара
// =============================================================

function ProgressBar({ progress }: { progress: number }) {
  return (
    <div className="w-full space-y-2">
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>Прогресс</span>
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full bg-primary transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

// =============================================================
// Основной компонент страницы импорта
// =============================================================

export default function ImportsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [status, setStatus] = useState<ImportStatus | null>(null);
  const [progress, setProgress] = useState(0);
  const [report, setReport] = useState<ImportBatch | null>(null);
  const [history, setHistory] = useState<ImportBatch[]>([]);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Загрузка истории импортов из API
  const loadHistory = useCallback(async () => {
    try {
      const response = await api.get<ImportBatch[]>("/imports");
      setHistory(response.data);
    } catch {
      // Игнорируем ошибку при загрузке истории
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Очистка интервала при размонтировании или завершении
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  // Поллинг статуса импорта
  useEffect(() => {
    if (!batchId || status === "completed" || status === "failed") {
      return;
    }

    intervalRef.current = setInterval(async () => {
      try {
        const response = await api.get<ImportBatch>(`/imports/${batchId}/status`);
        const batch = response.data;

        setStatus(batch.status as ImportStatus);
        setError(batch.review_notes || null);

        // Вычисляем прогресс
        if (batch.total_rows > 0) {
          const processed = batch.new_rows + batch.duplicates + batch.errors;
          setProgress(Math.min((processed / batch.total_rows) * 100, 100));
        }

        // Если завершено — сохраняем отчет и останавливаем поллинг
        if (batch.status === "completed" || batch.status === "failed") {
          setReport(batch);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
          }

          if (batch.status === "completed") {
            toast.success("Импорт завершён успешно!");
          } else {
            toast.error(`Импорт завершён с ошибками: ${batch.errors} строк`);
          }
        }
      } catch (err) {
        console.error("Ошибка поллинга:", err);
        // Не показываем toast при каждой ошибке поллинга
      }
    }, 2000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [batchId, status]);

  // Обработка выбора файла через dropzone
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    const selectedFile = acceptedFiles[0];

    if (!selectedFile.name.toLowerCase().endsWith(".xlsx")) {
      toast.error("Поддерживаются только файлы .xlsx");
      return;
    }

    setFile(selectedFile);
    uploadFile(selectedFile);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    },
    multiple: false,
  });

  // Загрузка файла на сервер
  const uploadFile = async (fileToUpload: File) => {
    setUploading(true);
    setError(null);
    setBatchId(null);
    setStatus(null);
    setProgress(0);
    setReport(null);

    const formData = new FormData();
    formData.append("file", fileToUpload);

    try {
      const response = await api.post<ImportBatch>("/imports/upload", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });

      const batch = response.data;
      setBatchId(batch.id);
      setStatus(batch.status as ImportStatus);
      setUploading(false);

      // Обновляем историю после загрузки
      loadHistory();
      toast.info("Файл принят на обработку");
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } }; message?: string };
      const message =
        axiosError.response?.data?.detail ||
        axiosError.message ||
        "Ошибка загрузки файла";
      setError(message);
      toast.error(message);
      setUploading(false);
    }
  };

  // Сброс формы
  const handleReset = () => {
    setFile(null);
    setBatchId(null);
    setStatus(null);
    setProgress(0);
    setReport(null);
    setError(null);
    setUploading(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }
  };

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Загрузка каталогов</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Загрузите Excel-каталог для пополнения базы масел и рекомендаций
        </p>
      </div>

      {/* Зона Drag & Drop */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Загрузить файл
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!batchId && !uploading ? (
            <div
              {...getRootProps()}
              className={`relative flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-12 transition-colors ${
                isDragActive
                  ? "border-primary bg-primary/5"
                  : "border-input hover:border-primary/50 hover:bg-muted/50"
              }`}
            >
              <input {...getInputProps()} />
              <FileSpreadsheet className="mb-4 h-12 w-12 text-muted-foreground" />
              <p className="text-base font-medium">
                {isDragActive
                  ? "Отпустите файл для загрузки"
                  : "Перетащите .xlsx файл сюда или нажмите для выбора"}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Поддерживаются файлы Excel (.xlsx)
              </p>
            </div>
          ) : uploading ? (
            <div className="flex flex-col items-center justify-center py-12 space-y-4">
              <Loader2 className="h-10 w-10 animate-spin text-primary" />
              <p className="text-base font-medium">Загрузка файла на сервер...</p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Прогресс и статус */}
      {batchId && status && !report && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Статус обработки
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <Badge
                variant="outline"
                className={STATUS_COLORS[status] || "bg-gray-100"}
              >
                {STATUS_LABELS[status] || status}
              </Badge>
              <span className="text-sm text-muted-foreground">{file?.name}</span>
            </div>

            <ProgressBar progress={progress} />

            {(status === "processing" || status === "pending") && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>
                  {status === "processing"
                    ? "Идёт анализ и нормализация данных..."
                    : "Задача в очереди на обработку..."}
                </span>
              </div>
            )}

            {error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700 border border-red-200">
                <AlertTriangle className="inline-block mr-2 h-4 w-4" />
                {error}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Итоговый отчёт */}
      {report && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-emerald-600" />
              Отчёт об импорте
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg bg-muted/50 p-4 space-y-1">
                <p className="text-sm text-muted-foreground">Всего строк</p>
                <p className="text-2xl font-bold">{report.total_rows}</p>
              </div>
              <div className="rounded-lg bg-emerald-50 p-4 space-y-1">
                <p className="text-sm text-emerald-700">✅ Добавлено</p>
                <p className="text-2xl font-bold text-emerald-700">{report.new_rows}</p>
              </div>
              <div className="rounded-lg bg-amber-50 p-4 space-y-1">
                <p className="text-sm text-amber-700">🟡 Дубликаты</p>
                <p className="text-2xl font-bold text-amber-700">{report.duplicates}</p>
              </div>
              <div className="rounded-lg bg-red-50 p-4 space-y-1">
                <p className="text-sm text-red-700">🔴 Ошибки</p>
                <p className="text-2xl font-bold text-red-700">{report.errors}</p>
              </div>
            </div>

            <Separator />

            <div className="flex gap-3">
              <Button onClick={handleReset} variant="outline">
                <Upload className="mr-2 h-4 w-4" />
                Загрузить ещё файл
              </Button>
              <Button onClick={loadHistory}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Обновить список каталогов
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* История импортов */}
      <Card>
        <CardHeader>
          <CardTitle>История импортов</CardTitle>
        </CardHeader>
        <CardContent>
          {history.length === 0 ? (
            <p className="text-center py-8 text-muted-foreground">
              Пока нет загруженных каталогов
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Файл</TableHead>
                  <TableHead>Статус</TableHead>
                  <TableHead className="text-right">Всего строк</TableHead>
                  <TableHead className="text-right">Добавлено</TableHead>
                  <TableHead className="text-right">Дубликаты</TableHead>
                  <TableHead className="text-right">Ошибки</TableHead>
                  <TableHead>Дата</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {history.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">{item.filename}</TableCell>
                    <TableCell>
                      <Badge
                        variant="outline"
                        className={STATUS_COLORS[item.status as ImportStatus] || "bg-gray-100"}
                      >
                        {STATUS_LABELS[item.status as ImportStatus] || item.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">{item.total_rows}</TableCell>
                    <TableCell className="text-right text-emerald-600 font-medium">
                      {item.new_rows}
                    </TableCell>
                    <TableCell className="text-right text-amber-600">
                      {item.duplicates}
                    </TableCell>
                    <TableCell className="text-right text-red-600">
                      {item.errors}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {new Date(item.created_at).toLocaleDateString("ru-RU")}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
