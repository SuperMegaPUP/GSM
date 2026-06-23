import { create } from "zustand";
import api from "@/lib/api";

// =============================================================
// Типы — соответствуют реальным ответам backend
// =============================================================

export type SubscriptionStatus = "ACTIVE" | "GRACE_PERIOD" | "SUSPENDED" | "BLOCKED";
export type PlanType = "BASIC" | "PRO" | "ENTERPRISE";

export interface SubscriptionData {
  id: string;
  company_id: string;
  plan_type: PlanType;
  status: SubscriptionStatus;
  start_date: string;
  end_date: string;
  grace_period_ends_at: string | null;
  monthly_price: number;
  currency: string;
  is_active: boolean;
  days_left: number | null;
}

export interface ActionItem {
  type: string;
  severity: string;
  message: string;
}

export interface DailyPlanData {
  id: string;
  company_id: string;
  plan_date: string;
  items: ActionItem[];
}

// =============================================================
// Хранилище подписки и аналитики (Zustand)
// =============================================================

interface SubscriptionState {
  subscription: SubscriptionData | null;
  dailyPlan: DailyPlanData | null;
  loading: boolean;
  error: string | null;

  fetchSubscription: () => Promise<void>;
  fetchDailyPlan: (force?: boolean) => Promise<void>;
  setDailyPlan: (plan: DailyPlanData) => void;
  checkStatus: () => Promise<void>;
  clear: () => void;
}

export const useSubscriptionStore = create<SubscriptionState>((set, get) => ({
  subscription: null,
  dailyPlan: null,
  loading: false,
  error: null,

  fetchSubscription: async () => {
    try {
      set({ loading: true, error: null });
      const response = await api.get<SubscriptionData>("/billing/subscription");
      set({ subscription: response.data, loading: false });
    } catch (error: any) {
      set({ loading: false });
      if (error.response?.status === 401 && typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        window.location.href = "/login";
        return;
      }
    }
  },

  fetchDailyPlan: async (force?: boolean) => {
    try {
      set({ error: null });
      const params = force ? { force: true } : undefined;
      const response = await api.get<DailyPlanData>("/analytics/daily-plan", { params });
      set({ dailyPlan: response.data });
    } catch {
      // Не ломаем UI если аналитика недоступна
    }
  },

  setDailyPlan: (plan) => {
    set({ dailyPlan: plan });
  },

  checkStatus: async () => {
    const { fetchSubscription, fetchDailyPlan } = get();
    await Promise.all([fetchSubscription(), fetchDailyPlan()]);
  },

  clear: () => {
    set({ subscription: null, dailyPlan: null, error: null });
  },
}));
