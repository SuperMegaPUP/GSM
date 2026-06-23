'use client';

/**
 * GSM Design System — ThemeSwitcher
 *
 * Compact theme picker — three color chips for three themes.
 * Place in top-right of header or in user menu dropdown.
 *
 * Usage:
 *   <ThemeSwitcher />
 *   <ThemeSwitcher size="lg" showLabels />
 */

import { useTheme, THEME_LABELS, type Theme } from './ThemeProvider';
import { useEffect, useState } from 'react';

interface ThemeSwitcherProps {
  size?: 'sm' | 'md' | 'lg';
  showLabels?: boolean;
  className?: string;
}

const CHIP_GRADIENTS: Record<Theme, string> = {
  'industrial-warm':
    'linear-gradient(135deg, oklch(0.985 0.004 75) 0%, oklch(0.45 0.09 195) 60%, oklch(0.62 0.13 50) 100%)',
  'onyx-terminal':
    'linear-gradient(135deg, oklch(0.14 0.005 250) 0%, oklch(0.72 0.13 195) 60%, oklch(0.78 0.15 75) 100%)',
  'arctic-tech':
    'linear-gradient(135deg, oklch(0.985 0.005 240) 0%, oklch(0.58 0.14 220) 60%, oklch(0.62 0.18 340) 100%)',
};

const SIZE_MAP = {
  sm: { chip: 'w-6 h-6', wrapper: 'p-1' },
  md: { chip: 'w-7 h-7', wrapper: 'p-1.5' },
  lg: { chip: 'w-9 h-9', wrapper: 'p-2' },
} as const;

export function ThemeSwitcher({
  size = 'md',
  showLabels = false,
  className = '',
}: ThemeSwitcherProps) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch
  useEffect(() => setMounted(true), []);

  const sizes = SIZE_MAP[size];

  if (!mounted) {
    return <div className={`${sizes.wrapper}`} aria-hidden />;
  }

  return (
    <div
      role="toolbar"
      aria-label="Тема оформления"
      className={`inline-flex items-center gap-1.5 rounded-lg border bg-[var(--surface-1)] shadow-sm backdrop-blur ${sizes.wrapper} ${className}`}
    >
      {showLabels && (
        <span className="px-2 text-xs font-medium uppercase tracking-wide text-[var(--sidebar-muted)]">
          Тема
        </span>
      )}
      {(Object.keys(THEME_LABELS) as Theme[]).map((t) => (
        <button
          key={t}
          onClick={() => setTheme(t)}
          aria-pressed={theme === t}
          aria-label={THEME_LABELS[t].ru}
          title={`${THEME_LABELS[t].ru} — ${THEME_LABELS[t].description}`}
          className={`${sizes.chip} rounded-md border-2 transition-transform duration-fast ease-out hover:scale-110`}
          style={{
            background: CHIP_GRADIENTS[t],
            borderColor: theme === t ? 'var(--foreground)' : 'var(--border)',
            transform: theme === t ? 'scale(1.1)' : undefined,
          }}
        >
          {theme === t && (
            <span
              className="block h-full w-full rounded-md"
              style={{
                boxShadow: '0 0 0 1px var(--foreground)',
                opacity: 0.3,
              }}
            />
          )}
        </button>
      ))}
    </div>
  );
}
