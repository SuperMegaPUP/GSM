'use client';

/**
 * GSM Design System — ThemeProvider
 *
 * Manages theme state with localStorage persistence and SSR-safe hydration.
 * Three themes available:
 *   - 'industrial-warm' (default) — warm off-white + teal + terracotta
 *   - 'onyx-terminal'              — dark graphite + neon teal + amber
 *   - 'arctic-tech'                — icy white + cyan + steel pink
 *
 * Usage:
 *   // app/providers.tsx
 *   <ThemeProvider>
 *     <App />
 *   </ThemeProvider>
 *
 *   // any component
 *   const { theme, setTheme } = useTheme();
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

export type Theme = 'industrial-warm' | 'onyx-terminal' | 'arctic-tech';

export const THEMES: Theme[] = [
  'industrial-warm',
  'onyx-terminal',
  'arctic-tech',
];

export const THEME_LABELS: Record<Theme, { ru: string; en: string; description: string }> = {
  'industrial-warm': {
    ru: 'Industrial Warm',
    en: 'Industrial Warm',
    description: 'Тёплая инженерная (по умолчанию)',
  },
  'onyx-terminal': {
    ru: 'Onyx Terminal',
    en: 'Onyx Terminal',
    description: 'Тёмная для работы вечером',
  },
  'arctic-tech': {
    ru: 'Arctic Tech',
    en: 'Arctic Tech',
    description: 'Минимализм Stripe-стиля',
  },
};

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

const STORAGE_KEY = 'gsm-theme';
const DEFAULT_THEME: Theme = 'industrial-warm';

// Inline script to set theme before hydration — prevents flash of wrong theme
export const themeScript = `
(function() {
  try {
    var t = localStorage.getItem('${STORAGE_KEY}') || '${DEFAULT_THEME}';
    document.documentElement.setAttribute('data-theme', t);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', '${DEFAULT_THEME}');
  }
})();
`;

interface ThemeProviderProps {
  children: React.ReactNode;
  defaultTheme?: Theme;
}

export function ThemeProvider({
  children,
  defaultTheme = DEFAULT_THEME,
}: ThemeProviderProps) {
  const [theme, setThemeState] = useState<Theme>(defaultTheme);

  // Hydrate from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
      if (stored && THEMES.includes(stored)) {
        setThemeState(stored);
        document.documentElement.setAttribute('data-theme', stored);
      } else {
        document.documentElement.setAttribute('data-theme', defaultTheme);
      }
    } catch {
      document.documentElement.setAttribute('data-theme', defaultTheme);
    }
  }, [defaultTheme]);

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    document.documentElement.setAttribute('data-theme', next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // ignore — private mode / disabled storage
    }
  }, []);

  const toggleTheme = useCallback(() => {
    const currentIndex = THEMES.indexOf(theme);
    const next = THEMES[(currentIndex + 1) % THEMES.length];
    setTheme(next);
  }, [theme, setTheme]);

  const value = useMemo(
    () => ({ theme, setTheme, toggleTheme }),
    [theme, setTheme, toggleTheme],
  );

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within <ThemeProvider>');
  }
  return ctx;
}
