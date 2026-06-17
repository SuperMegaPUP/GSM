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
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
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
