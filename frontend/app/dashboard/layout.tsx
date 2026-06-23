"use client";

import { useEffect, useState, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Search,
  Upload,
  Users,
  Bot,
  Menu,
  LogOut,
  ChevronDown,
  Settings,
  Droplets,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { getMe } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import { useSubscriptionStore } from "@/store/subscription-store";
import { GracePeriodBanner } from "@/components/banners/GracePeriodBanner";
import { SuspendedBanner } from "@/components/banners/SuspendedBanner";
import { toast } from "sonner";

import {
  Sidebar,
  type NavSection,
} from "@/components/ui/gsm/Sidebar";
import { PageTransition } from "@/components/ui/gsm/PageTransition";
import { ThemeSwitcher } from "@/components/ui/gsm/ThemeSwitcher";
import {
  CommandPalette,
  type Command,
} from "@/components/ui/gsm/CommandPalette";
import { useTheme } from "@/components/ui/gsm/ThemeProvider";

// =============================================================
// Навигация
// =============================================================

const NAV_SECTIONS: NavSection[] = [
  {
    label: "Основное",
    items: [
      { href: "/dashboard/search", label: "Подбор масел", icon: <Search /> },
      { href: "/dashboard/imports", label: "Загрузка каталогов", icon: <Upload /> },
      { href: "/dashboard/clients", label: "Клиенты", icon: <Users /> },
      { href: "/dashboard/sales-copilot", label: "Sales Copilot", icon: <Bot /> },
    ],
  },
];



// =============================================================
// Мобильное меню (Sheet)
// =============================================================

function MobileSidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <span>
            <Button variant="ghost" size="icon" className="md:hidden">
              <Menu className="h-5 w-5" />
            </Button>
          </span>
        }
      />
      <SheetContent side="left" className="w-64 p-0">
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle className="flex items-center gap-2">
            <Droplets className="h-5 w-5 text-primary" />
            GSM
          </SheetTitle>
        </SheetHeader>
        <nav className="space-y-1 p-2">
          {NAV_SECTIONS[0].items.map((item) => {
            const isActive = pathname === item.href;
            return (
              <a
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex h-9 items-center gap-3 rounded-lg px-3 text-sm transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground font-medium"
                    : "text-foreground hover:bg-accent/50",
                )}
              >
                <span className="[&>svg]:h-4 [&>svg]:w-4">{item.icon}</span>
                {item.label}
              </a>
            );
          })}
        </nav>
      </SheetContent>
    </Sheet>
  );
}

// =============================================================
// Верхняя панель
// =============================================================

function TopNav({ onToggle }: { collapsed?: boolean; onToggle: () => void }) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const initials = user?.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "??";

  return (
    <header className="flex h-14 items-center gap-4 border-b px-4">
      <Button
        variant="ghost"
        size="icon"
        className="hidden md:flex"
        onClick={onToggle}
      >
        <Menu className="h-4 w-4" />
      </Button>

      <MobileSidebar />

      {/* ThemeSwitcher */}
      <div className="ml-2">
        <ThemeSwitcher size="sm" />
      </div>

      <div className="flex-1" />

      {user && (
        <div className="flex items-center gap-3">
          <Badge
            variant="outline"
            className={cn(
              "hidden sm:inline-flex",
              user.role === "admin" && "border-blue-400 text-blue-600",
              user.role === "supervisor" && "border-purple-400 text-purple-600",
            )}
          >
            {user.role === "admin"
              ? "Админ"
              : user.role === "supervisor"
                ? "Супервайзер"
                : user.role === "manager"
                  ? "Менеджер"
                  : "Технолог"}
          </Badge>

          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <span>
                  <Button variant="ghost" className="flex items-center gap-2 px-2">
                    <Avatar className="h-7 w-7">
                      <AvatarFallback className="text-xs">{initials}</AvatarFallback>
                    </Avatar>
                    <span className="hidden text-sm sm:inline">{user.full_name}</span>
                    <ChevronDown className="h-3 w-3 text-muted-foreground" />
                  </Button>
                </span>
              }
            />
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel>{user.email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => toast.info("Настройки — в разработке")}>
                <Settings className="mr-2 h-4 w-4" />
                Настройки
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={logout}>
                <LogOut className="mr-2 h-4 w-4" />
                Выйти
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
    </header>
  );
}

// =============================================================
// Команды для CommandPalette
// =============================================================

function useCommands() {
  const router = useRouter();
  const { setTheme } = useTheme();

  const commands: Command[] = [
    {
      id: "go-search",
      title: "Подобрать масло",
      subtitle: "Перейти к форме подбора",
      group: "Действия",
      action: () => router.push("/dashboard/search"),
      shortcut: "⏎",
    },
    {
      id: "go-imports",
      title: "Загрузить каталог",
      subtitle: "Импорт Excel в БД",
      group: "Действия",
      action: () => router.push("/dashboard/imports"),
    },
    {
      id: "go-clients",
      title: "Клиенты",
      subtitle: "Управление клиентами",
      group: "Действия",
      action: () => router.push("/dashboard/clients"),
    },
    {
      id: "go-sales-copilot",
      title: "Sales Copilot",
      subtitle: "Отработка возражений",
      group: "Действия",
      action: () => router.push("/dashboard/sales-copilot"),
    },
    {
      id: "theme-industrial",
      title: "Industrial Warm",
      subtitle: "Тёплая инженерная тема",
      group: "Тема",
      action: () => setTheme("industrial-warm"),
    },
    {
      id: "theme-onyx",
      title: "Onyx Terminal",
      subtitle: "Тёмная для работы вечером",
      group: "Тема",
      action: () => setTheme("onyx-terminal"),
    },
    {
      id: "theme-arctic",
      title: "Arctic Tech",
      subtitle: "Минимализм Stripe-стиля",
      group: "Тема",
      action: () => setTheme("arctic-tech"),
    },
  ];

  return commands;
}

// =============================================================
// Основной лэйаут
// =============================================================

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, isLoading, setAuth, hydrate } = useAuthStore();
  const subscription = useSubscriptionStore((s) => s.subscription);
  const checkStatus = useSubscriptionStore((s) => s.checkStatus);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const commands = useCommands();

  const handleLogout = useCallback(() => {
    useAuthStore.getState().logout();
  }, []);

  useEffect(() => {
    hydrate();

    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    if (!user) {
      getMe()
        .then((u) => {
          setAuth(u, token);
          checkStatus();
        })
        .catch(() => {
          localStorage.removeItem("access_token");
          router.replace("/login");
        });
    } else {
      checkStatus();
    }
  }, []);

  useEffect(() => {
    if (subscription && !subscription.is_active && !pathname.startsWith("/billing")) {
      router.replace("/billing/suspended");
    }
  }, [subscription, pathname, router]);

  if (isLoading && !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  if (!isAuthenticated && !isLoading) {
    return null;
  }

  const sidebarUser = user
    ? {
        name: user.full_name,
        role:
          user.role === "admin"
            ? "Админ"
            : user.role === "supervisor"
              ? "Супервайзер"
              : user.role === "manager"
                ? "Менеджер"
                : "Технолог",
        initials: user.full_name
          .split(" ")
          .map((n: string) => n[0])
          .join("")
          .toUpperCase()
          .slice(0, 2),
      }
    : undefined;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Боковая панель (десктоп) */}
      <div className="hidden md:flex">
        <Sidebar
          sections={NAV_SECTIONS}
          user={sidebarUser}
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed((v) => !v)}
          onLogout={handleLogout}
        />
      </div>

      {/* Основная область */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopNav
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed((v) => !v)}
        />
        <GracePeriodBanner />
        <SuspendedBanner />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          <PageTransition>{children}</PageTransition>
        </main>
      </div>

      {/* Глобальная CommandPalette */}
      <CommandPalette commands={commands} />
    </div>
  );
}
