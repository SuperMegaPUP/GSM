import type { Config } from 'tailwindcss';

/**
 * GSM Design System — Tailwind config
 * Three themes via data-theme attribute + CSS variables (see tokens.css)
 *
 * Usage in app:
 *   <html data-theme="industrial-warm">  // default
 *   <html data-theme="onyx-terminal">    // dark
 *   <html data-theme="arctic-tech">      // arctic
 *
 * All colors reference CSS variables, so theme switching
 * requires NO re-render — pure CSS cascade.
 */
const config: Config = {
  darkMode: ['class', '[data-theme="onyx-terminal"]'],
  content: [
    './app/**/*.{ts,tsx,mdx}',
    './components/**/*.{ts,tsx,mdx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      // ─── Colors: all wired to CSS variables ───────────────────
      colors: {
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        surface: {
          1: 'var(--surface-1)',
          2: 'var(--surface-2)',
          3: 'var(--surface-3)',
        },
        primary: {
          DEFAULT: 'var(--primary)',
          hover: 'var(--primary-hover)',
          foreground: 'var(--primary-foreground)',
          muted: 'var(--primary-muted)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          hover: 'var(--accent-hover)',
          foreground: 'var(--accent-foreground)',
          muted: 'var(--accent-muted)',
        },
        success: {
          DEFAULT: 'var(--success)',
          muted: 'var(--success-muted)',
        },
        warning: {
          DEFAULT: 'var(--warning)',
          muted: 'var(--warning-muted)',
        },
        destructive: {
          DEFAULT: 'var(--destructive)',
          muted: 'var(--destructive-muted)',
        },
        info: {
          DEFAULT: 'var(--info)',
          muted: 'var(--info-muted)',
        },
        sidebar: {
          DEFAULT: 'var(--sidebar)',
          foreground: 'var(--sidebar-foreground)',
          muted: 'var(--sidebar-muted)',
          accent: 'var(--sidebar-accent)',
          border: 'var(--sidebar-border)',
        },
        border: {
          DEFAULT: 'var(--border)',
          strong: 'var(--border-strong)',
        },
        // Node type semantic groups
        node: {
          engine: 'var(--node-engine)',
          'engine-bg': 'var(--node-engine-bg)',
          transmission: 'var(--node-transmission)',
          'transmission-bg': 'var(--node-transmission-bg)',
          drivetrain: 'var(--node-drivetrain)',
          'drivetrain-bg': 'var(--node-drivetrain-bg)',
          fluids: 'var(--node-fluids)',
          'fluids-bg': 'var(--node-fluids-bg)',
          brakes: 'var(--node-brakes)',
          'brakes-bg': 'var(--node-brakes-bg)',
        },
      },

      // ─── Typography ────────────────────────────────────────────
      fontFamily: {
        sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
        xs:   ['var(--text-xs)', { lineHeight: '1rem' }],
        sm:   ['var(--text-sm)', { lineHeight: '1.25rem' }],
        base: ['var(--text-base)', { lineHeight: '1.45rem' }],
        md:   ['var(--text-md)', { lineHeight: '1.5rem' }],
        lg:   ['var(--text-lg)', { lineHeight: '1.75rem' }],
        xl:   ['var(--text-xl)', { lineHeight: '1.75rem' }],
        '2xl': ['var(--text-2xl)', { lineHeight: '2rem' }],
        '3xl': ['var(--text-3xl)', { lineHeight: '2.25rem' }],
        '4xl': ['var(--text-4xl)', { lineHeight: '2.5rem' }],
        '5xl': ['var(--text-5xl)', { lineHeight: '1' }],
      },
      letterSpacing: {
        tight: 'var(--tracking-tight)',
        normal: 'var(--tracking-normal)',
        wide: 'var(--tracking-wide)',
        mono: 'var(--tracking-mono)',
      },

      // ─── Radius ────────────────────────────────────────────────
      borderRadius: {
        xs: 'var(--radius-xs)',
        sm: 'var(--radius-sm)',
        DEFAULT: 'var(--radius-md)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
        '2xl': 'var(--radius-2xl)',
        full: 'var(--radius-full)',
      },

      // ─── Shadows ───────────────────────────────────────────────
      boxShadow: {
        xs: 'var(--shadow-xs)',
        sm: 'var(--shadow-sm)',
        DEFAULT: 'var(--shadow-md)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
        '2xl': 'var(--shadow-2xl)',
        glow: 'var(--shadow-glow)',
      },

      // ─── Spacing (comfortable density) ────────────────────────
      spacing: {
        1: 'var(--space-1)',
        2: 'var(--space-2)',
        3: 'var(--space-3)',
        4: 'var(--space-4)',
        5: 'var(--space-5)',
        6: 'var(--space-6)',
        8: 'var(--space-8)',
        10: 'var(--space-10)',
        12: 'var(--space-12)',
        16: 'var(--space-16)',
        20: 'var(--space-20)',
        24: 'var(--space-24)',
      },

      // ─── Z-index scale ────────────────────────────────────────
      zIndex: {
        base: 'var(--z-base)',
        dropdown: 'var(--z-dropdown)',
        sticky: 'var(--z-sticky)',
        overlay: 'var(--z-overlay)',
        modal: 'var(--z-modal)',
        toast: 'var(--z-toast)',
        tooltip: 'var(--z-tooltip)',
      },

      // ─── Transition ───────────────────────────────────────────
      transitionDuration: {
        fast: 'var(--duration-fast)',
        DEFAULT: 'var(--duration-base)',
        slow: 'var(--duration-slow)',
        slower: 'var(--duration-slower)',
      },
      transitionTimingFunction: {
        out: 'var(--ease-out)',
        'in-out': 'var(--ease-in-out)',
        spring: 'var(--ease-spring)',
      },

      // ─── Keyframes ────────────────────────────────────────────
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.96)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        typing: {
          '0%, 60%, 100%': { opacity: '0.3', transform: 'translateY(0)' },
          '30%': { opacity: '1', transform: 'translateY(-3px)' },
        },
      },
      animation: {
        'fade-up': 'fade-up var(--duration-slow) var(--ease-out)',
        'fade-in': 'fade-in var(--duration-base) var(--ease-out)',
        'scale-in': 'scale-in var(--duration-slow) var(--ease-spring)',
        shimmer: 'shimmer 1.5s infinite',
        typing: 'typing 1.4s infinite',
      },
    },
  },
  plugins: [
    require('tailwindcss-animate'),
  ],
};

export default config;
