"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { getMe } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

// =============================================================
// Навигация
// =============================================================

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { href: "/dashboard", label: "Подбор масел", icon: Search },
  { href: "/dashboard/imports", label: "Загрузка каталогов", icon: Upload },
  { href: "/dashboard/clients", label: "Клиенты", icon: Users },
  { href: "/dashboard/sales-copilot", label: "AI-Суфлёр", icon: Bot },
];

const subscriptionColors: Record<string, string> = {
  active: "bg-emerald-500",
  grace_period: "bg-amber-500",
  suspended: "bg-red-500",
  blocked: "bg-red-700",
};



// =============================================================
// Боковая панель (десктоп)
// =============================================================

function Sidebar({ collapsed }: { collapsed: boolean }) {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r bg-sidebar transition-all duration-200",
        collapsed ? "w-16" : "w-56",
      )}
    >
      {/* Логотип */}
      <div
        className={cn(
          "flex h-14 items-center border-b px-4",
          collapsed ? "justify-center" : "gap-3",
        )}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold">
          G
        </div>
        {!collapsed && (
          <span className="text-sm font-semibold truncate">GSM</span>
        )}
      </div>

      {/* Навигация */}
      <nav className="flex-1 space-y-1 p-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return collapsed ? (
            <Tooltip key={item.href}>
              <TooltipTrigger
                render={
                  <Link
                    href={item.href}
                    className={cn(
                      "flex h-9 w-full items-center justify-center rounded-lg text-sm transition-colors",
                      isActive
                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                        : "text-sidebar-foreground hover:bg-sidebar-accent/50",
                    )}
                  >
                    <item.icon className="h-4 w-4" />
                  </Link>
                }
              />
              <TooltipContent side="right">{item.label}</TooltipContent>
            </Tooltip>
          ) : (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex h-9 items-center gap-3 rounded-lg px-3 text-sm transition-colors",
                isActive
                  ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/50",
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Подпись снизу */}
      {!collapsed && user && (
        <div className="border-t p-3">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                subscriptionColors[user.role] || "bg-gray-400",
              )}
            />
            <span className="text-xs text-muted-foreground">
              {user.full_name}
            </span>
          </div>
        </div>
      )}
    </aside>
  );
}

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
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
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
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
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
      {/* Кнопка сворачивания (десктоп) */}
      <Button
        variant="ghost"
        size="icon"
        className="hidden md:flex"
        onClick={onToggle}
      >
        <Menu className="h-4 w-4" />
      </Button>

      {/* Мобильное меню */}
      <MobileSidebar />

      {/* Заголовок страницы */}
      <div className="flex-1" />

      {/* Профиль */}
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
// Основной лэйаут
// =============================================================

import { toast } from "sonner";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, setAuth, hydrate } = useAuthStore();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  useEffect(() => {
    hydrate();

    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }

    if (!user) {
      getMe()
        .then((u) => setAuth(u, token))
        .catch(() => {
          localStorage.removeItem("access_token");
          router.replace("/login");
        });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Боковая панель (десктоп) */}
      <div className="hidden md:flex">
        <Sidebar collapsed={sidebarCollapsed} />
      </div>

      {/* Основная область */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopNav
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed((v) => !v)}
        />
        <main className="flex-1 overflow-y-auto p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
