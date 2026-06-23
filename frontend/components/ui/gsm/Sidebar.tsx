'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { type ReactNode } from 'react';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

export interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  badge?: string;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

interface SidebarProps {
  sections: NavSection[];
  user?: {
    name: string;
    role: string;
    initials: string;
  };
  onLogout?: () => void;
  collapsed?: boolean;
  onToggle?: () => void;
}

export function Sidebar({
  sections,
  user,
  onLogout,
  collapsed = false,
  onToggle,
}: SidebarProps) {
  const pathname = usePathname();

  // Collapse state is managed by the parent component

  return (
    <aside
      className="sticky top-0 flex h-screen flex-col border-r bg-[var(--sidebar)] text-[var(--sidebar-foreground)] transition-all duration-200 ease-out"
      style={{ width: collapsed ? '3.5rem' : '16rem' }}
    >
      {/* Brand + toggle */}
      <div className="flex items-center gap-3 px-3 pt-3 pb-2" style={{ minHeight: '3rem' }}>
        {collapsed ? (
          <button
            onClick={onToggle}
            className="brand-mark grid h-9 w-9 place-items-center text-base"
            aria-label="Развернуть меню"
          >
            G
          </button>
        ) : (
          <>
            <button
              onClick={onToggle}
              className="brand-mark grid h-9 w-9 flex-shrink-0 place-items-center text-base"
              aria-label="Свернуть меню"
            >
              G
            </button>
            <div className="flex-1 overflow-hidden">
              <div className="truncate text-base font-semibold tracking-tight">
                GSM
                <span className="ml-1 font-mono text-xs opacity-70">v1.0</span>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Nav sections */}
      <nav className="flex-1 overflow-y-auto px-2">
        {sections.map((section) => (
          <div key={section.label} className="mb-5">
            {!collapsed && (
              <div className="mb-1 px-3 text-xs font-medium uppercase tracking-wide text-[var(--sidebar-muted)]">
                {section.label}
              </div>
            )}
            {section.items.map((item) => {
              const isActive =
                pathname === item.href ||
                pathname?.startsWith(item.href + '/');
              const navEl = (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? 'page' : undefined}
                  data-active={isActive}
                  className="nav-item mb-0.5 flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors"
                  style={{
                    justifyContent: collapsed ? 'center' : undefined,
                    paddingLeft: collapsed ? '0.5rem' : undefined,
                    paddingRight: collapsed ? '0.5rem' : undefined,
                  }}
                >
                  <span
                    className="flex-shrink-0 opacity-85 [&>svg]:h-[18px] [&>svg]:w-[18px]"
                  >
                    {item.icon}
                  </span>
                  {!collapsed && (
                    <>
                      <span className="truncate">{item.label}</span>
                      {item.badge && (
                        <span className="ml-auto rounded-full bg-[var(--sidebar-accent)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--accent-foreground)]">
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </Link>
              );

              if (collapsed) {
                return (
                  <Tooltip key={item.href}>
                    <TooltipTrigger render={<span>{navEl}</span>} />
                    <TooltipContent side="right" sideOffset={8}>
                      {item.label}
                      {item.badge && ` (${item.badge})`}
                    </TooltipContent>
                  </Tooltip>
                );
              }
              return navEl;
            })}
          </div>
        ))}
      </nav>

      {/* User footer */}
      {user && (
        <div
          className="mt-auto flex items-center border-t border-[var(--sidebar-border)] p-2"
          style={{ justifyContent: collapsed ? 'center' : undefined }}
        >
          <div
            className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full text-xs font-semibold text-[var(--accent-foreground)]"
            style={{ background: 'linear-gradient(135deg, var(--accent), var(--primary))' }}
          >
            {user.initials}
          </div>
          {!collapsed && (
            <>
              <div className="min-w-0 flex-1 ml-3">
                <div className="truncate text-sm font-medium leading-tight">{user.name}</div>
                <div className="truncate text-xs text-[var(--sidebar-muted)]">{user.role}</div>
              </div>
              {onLogout && (
                <button
                  onClick={onLogout}
                  aria-label="Выход"
                  className="rounded-md border border-[var(--sidebar-border)] p-1.5 text-[var(--sidebar-foreground)] transition-colors hover:bg-white/5"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                    <polyline points="16 17 21 12 16 7" />
                    <line x1="21" y1="12" x2="9" y2="12" />
                  </svg>
                </button>
              )}
            </>
          )}
        </div>
      )}
    </aside>
  );
}
