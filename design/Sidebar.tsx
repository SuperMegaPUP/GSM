'use client';

/**
 * GSM Design System — Sidebar
 *
 * Dark sidebar with brand mark, grouped nav, active indicator, user footer.
 * Theme-aware: uses --sidebar-* tokens.
 *
 * Nav items use simple aria-current for active state.
 * Icons: lucide-react (install: npm i lucide-react)
 */

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';

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
}

export function Sidebar({ sections, user, onLogout }: SidebarProps) {
  const pathname = usePathname();

  return (
    <aside className="sticky top-0 flex h-screen w-64 flex-col border-r bg-[var(--sidebar)] p-3 text-[var(--sidebar-foreground)]">
      {/* Brand */}
      <div className="mb-8 flex items-center gap-3 px-3">
        <div className="brand-mark h-9 w-9 text-base">G</div>
        <div>
          <div className="text-base font-semibold tracking-tight">
            GSM
            <span className="ml-1 font-mono text-xs opacity-70">v1.0</span>
          </div>
        </div>
      </div>

      {/* Nav sections */}
      <nav className="flex-1 overflow-y-auto">
        {sections.map((section) => (
          <div key={section.label} className="mb-6">
            <div className="mb-1 px-3 text-xs font-medium uppercase tracking-wide text-[var(--sidebar-muted)]">
              {section.label}
            </div>
            {section.items.map((item) => {
              const isActive =
                pathname === item.href ||
                pathname?.startsWith(item.href + '/');
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? 'page' : undefined}
                  data-active={isActive}
                  className="nav-item mb-0.5"
                >
                  <span className="flex-shrink-0 opacity-85 [&>svg]:h-[18px] [&>svg]:w-[18px]">
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ml-auto rounded-full bg-[var(--sidebar-accent)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--accent-foreground)]">
                      {item.badge}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* User footer */}
      {user && (
        <div className="mt-auto flex items-center gap-3 border-t border-[var(--sidebar-border)] p-3">
          <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full text-xs font-semibold text-[var(--accent-foreground)]"
               style={{ background: 'linear-gradient(135deg, var(--accent), var(--primary))' }}>
            {user.initials}
          </div>
          <div className="min-w-0 flex-1">
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
        </div>
      )}
    </aside>
  );
}
