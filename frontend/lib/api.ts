import axios from "axios";

// =============================================================
// Axios-клиент с автоматической подстановкой JWT
// =============================================================

const api = axios.create({
  baseURL: "/api/v1",
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    // Сохраняем X-Grace-Days-Left для отображения баннера
    const graceHeader = response.headers?.["x-grace-days-left"];
    if (graceHeader && typeof window !== "undefined") {
      localStorage.setItem("grace_days_left", String(graceHeader));
    }
    return response;
  },
  (error) => {
    // 401 — перенаправляем на логин
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("subscription_status");
      localStorage.removeItem("grace_days_left");
      window.location.href = "/login";
    }

    // 402 — подписка приостановлена, редирект на страницу
    if (error.response?.status === 402 && typeof window !== "undefined") {
      localStorage.setItem("subscription_status", "SUSPENDED");
      const graceHeader = error.response.headers?.["x-grace-days-left"];
      if (graceHeader) {
        localStorage.setItem("grace_days_left", String(graceHeader));
      }
      window.location.href = "/billing/suspended";
      return Promise.reject(error);
    }

    // Нормализация ошибок: превращаем объект в строку
    if (error.response?.data?.detail) {
      const detail = error.response.data.detail;
      let message: string;

      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail
          .map((err: unknown) => {
            const e = err as { loc?: string[]; msg?: string };
            return `${(e.loc ?? []).slice(-1)[0] || "поле"}: ${e.msg ?? ""}`;
          })
          .join("; ");
      } else if (typeof detail === "object" && detail !== null) {
        const d = detail as Record<string, unknown>;
        message = String(d.msg ?? d.detail ?? JSON.stringify(detail));
      } else {
        message = String(detail);
      }

      error.message = message;
    } else if (!error.message) {
      error.message = "Произошла ошибка";
    }

    return Promise.reject(error);
  },
);

export default api;

// =============================================================
// Типизированные API-методы
// =============================================================

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  full_name: string;
  role: string;
  company_id: string;
}

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>("/auth/login", body);
  return response.data;
}

export async function getMe(): Promise<UserResponse> {
  const response = await api.get<UserResponse>("/auth/me");
  return response.data;
}

export async function register(body: LoginRequest & { full_name: string }): Promise<UserResponse> {
  const response = await api.post<UserResponse>("/auth/register", body);
  return response.data;
}

// =============================================================
// Типы для каталога (марки/модели)
// =============================================================

export interface CarBrandRead {
  id: string;
  name_ru: string;
  name_en: string | null;
  country: string | null;
}

export interface CarModelRead {
  id: string;
  brand_id: string;
  name: string;
  generation: string | null;
  year_start: number | null;
  year_end: number | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// =============================================================
// API-методы для каталога
// =============================================================

export async function getBrands(search?: string, limit = 50): Promise<PaginatedResponse<CarBrandRead>> {
  const params: Record<string, string | number> = { limit };
  if (search) params.search = search;
  const response = await api.get<PaginatedResponse<CarBrandRead>>("/catalog/brands", { params });
  return response.data;
}

export async function getModels(brandId?: string, search?: string, limit = 50): Promise<PaginatedResponse<CarModelRead>> {
  const params: Record<string, string | number> = { limit };
  if (brandId) params.brand_id = brandId;
  if (search) params.search = search;
  const response = await api.get<PaginatedResponse<CarModelRead>>("/catalog/models", { params });
  return response.data;
}
