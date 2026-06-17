import { create } from "zustand";
import type { UserResponse } from "@/lib/api";

// =============================================================
// Хранилище аутентификации (Zustand)
// =============================================================

interface AuthState {
  user: UserResponse | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  setAuth: (user: UserResponse, token: string) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,

  setAuth: (user, token) => {
    localStorage.setItem("access_token", token);
    set({ user, token, isAuthenticated: true, isLoading: false });
  },

  logout: () => {
    localStorage.removeItem("access_token");
    set({ user: null, token: null, isAuthenticated: false, isLoading: false });
    window.location.href = "/login";
  },

  setLoading: (loading) => set({ isLoading: loading }),

  hydrate: () => {
    const token = localStorage.getItem("access_token");
    if (token) {
      set({ token, isAuthenticated: true, isLoading: true });
    } else {
      set({ isLoading: false });
    }
  },
}));
