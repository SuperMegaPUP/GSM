'use client';

/**
 * GSM Design System — CommandPalette
 *
 * Linear/Raycast-style command palette with ⌘K / Ctrl+K shortcut.
 * Supports nested groups, fuzzy search, keyboard navigation.
 *
 * Usage:
 *   <CommandPalette
 *     commands={[
 *       {
 *         id: 'search',
 *         title: 'Подобрать масло',
 *         subtitle: 'Перейти к форме подбора',
 *         group: 'Действия',
 *         icon: <SearchIcon />,
 *         action: () => router.push('/dashboard/search'),
 *         shortcut: '⏎',
 *       },
 *       ...
 *     ]}
 *   />
 */

import { AnimatePresence, motion } from 'framer-motion';
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

export interface Command {
  id: string;
  title: string;
  subtitle?: string;
  group: string;
  icon?: ReactNode;
  action: () => void;
  shortcut?: string;
  keywords?: string;
}

interface CommandPaletteProps {
  commands: Command[];
  placeholder?: string;
}

export function CommandPalette({
  commands,
  placeholder = 'Найти команду, страницу или масло...',
}: CommandPaletteProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // ⌘K / Ctrl+K to toggle
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      }
      if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, []);

  // Focus input on open
  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Filter
  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter((c) =>
      [c.title, c.subtitle, c.group, c.keywords]
        .filter(Boolean)
        .some((s) => s!.toLowerCase().includes(q))
    );
  }, [commands, query]);

  // Group commands preserving order
  const grouped = useMemo(() => {
    const map = new Map<string, Command[]>();
    filtered.forEach((cmd) => {
      if (!map.has(cmd.group)) map.set(cmd.group, []);
      map.get(cmd.group)!.push(cmd);
    });
    return Array.from(map.entries());
  }, [filtered]);

  // Flatten for keyboard navigation
  const flat = useMemo(() => grouped.flatMap(([, items]) => items), [grouped]);

  // Reset active index when query changes
  useEffect(() => setActiveIndex(0), [query]);

  // Keyboard nav
  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, flat.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const cmd = flat[activeIndex];
        if (cmd) {
          cmd.action();
          setOpen(false);
        }
      }
    },
    [flat, activeIndex],
  );

  // Scroll active into view
  useEffect(() => {
    const el = listRef.current?.querySelector(`[data-idx="${activeIndex}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [activeIndex]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-[var(--z-modal)] flex items-start justify-center bg-[oklch(0.10_0.005_250_/_0.6)] backdrop-blur"
          style={{ paddingTop: '12vh' }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          onClick={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <motion.div
            className="w-[90%] max-w-[36rem] overflow-hidden rounded-xl border bg-[var(--surface-1)] shadow-2xl"
            initial={{ scale: 0.98, y: -8, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.98, y: -8, opacity: 0 }}
            transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
            onKeyDown={onKeyDown}
          >
            {/* Input */}
            <div className="flex items-center gap-3 border-b px-5 py-4">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--sidebar-muted)"
                strokeWidth="2"
              >
                <circle cx="11" cy="11" r="8" />
                <path d="m21 21-4.3-4.3" />
              </svg>
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={placeholder}
                className="flex-1 bg-transparent text-base outline-none placeholder:text-[var(--sidebar-muted)]"
              />
              <kbd className="kbd">ESC</kbd>
            </div>

            {/* List */}
            <div
              ref={listRef}
              className="max-h-[24rem] overflow-y-auto p-2"
            >
              {flat.length === 0 && (
                <div className="px-3 py-8 text-center text-sm text-[var(--sidebar-muted)]">
                  Ничего не найдено по запросу «{query}»
                </div>
              )}
              {grouped.map(([group, items]) => (
                <div key={group}>
                  <div className="px-3 pb-1 pt-2 text-xs font-medium uppercase tracking-wide text-[var(--sidebar-muted)]">
                    {group}
                  </div>
                  {items.map((cmd) => {
                    const idx = flat.indexOf(cmd);
                    const isActive = idx === activeIndex;
                    return (
                      <button
                        key={cmd.id}
                        data-idx={idx}
                        onClick={() => {
                          cmd.action();
                          setOpen(false);
                        }}
                        onMouseEnter={() => setActiveIndex(idx)}
                        className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left transition-colors"
                        style={{
                          background: isActive ? 'var(--surface-2)' : 'transparent',
                        }}
                      >
                        {cmd.icon && (
                          <span
                            className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-md"
                            style={{
                              background: 'var(--primary-muted)',
                              color: 'var(--primary)',
                            }}
                          >
                            {cmd.icon}
                          </span>
                        )}
                        <span className="flex flex-1 flex-col">
                          <span className="text-sm font-medium">{cmd.title}</span>
                          {cmd.subtitle && (
                            <span className="text-xs text-[var(--sidebar-muted)]">
                              {cmd.subtitle}
                            </span>
                          )}
                        </span>
                        {cmd.shortcut && <kbd className="kbd">{cmd.shortcut}</kbd>}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
