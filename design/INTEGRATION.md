# GSM Design System — Инструкция по интеграции

> **Готовая дизайн-система** для проекта GSM (Get Some Motor oil).
> 3 темы, типографика, компоненты, анимации. Без внешних UI-китов.
> Совместимо с текущим стеком: Next.js 14 + Tailwind + Framer Motion.

## 📦 Что в коробке

```
gsm-design-system/
├── preview.html              ← ИНТЕРАКТИВНОЕ ДЕМО (открыть в браузере!)
├── tokens.css                ← Design tokens для всех 3 тем
├── globals.css               ← Tailwind layer + базовые стили
├── tailwind.config.ts        ← Расширенный конфиг Tailwind
├── INTEGRATION.md            ← Этот файл
└── components/
    ├── ThemeProvider.tsx     ← Контекст + localStorage
    ├── ThemeSwitcher.tsx     ← Чипы переключения тем
    ├── CommandPalette.tsx    ← Cmd+K палитра
    ├── Dialog.tsx            ← Модалка с spring-анимацией
    ├── FluidCard.tsx         ← Карточка масла (главный компонент)
    ├── Sidebar.tsx           ← Боковое меню
    ├── PageTransition.tsx    ← Анимация перехода страниц
    └── nodeTypes.tsx         ← Конфиг типов узлов + иконки
```

## 🎨 Три темы

| Тема | data-theme | Когда использовать |
|---|---|---|
| **Industrial Warm** | `industrial-warm` | По умолчанию. Тёплый off-white + deep teal + terracotta |
| **Onyx Terminal** | `onyx-terminal` | Тёмная. Графит + neon teal + amber. Для работы вечером |
| **Arctic Tech** | `arctic-tech` | Холодная бело-голубая + cyan + steel pink |

Переключение тем — мгновенное, без перезагрузки. Через CSS variables + `data-theme` на `<html>`.

## 🚀 Шаги интеграции (для локальной модели-кодера)

### Шаг 1. Установить зависимости

```bash
npm install framer-motion lucide-react
```

### Шаг 2. Скопировать файлы

```bash
# Из этой папки в корень frontend-проекта:
cp tokens.css frontend/app/styles/tokens.css
cp globals.css frontend/app/globals.css  # перезапишет текущий
cp tailwind.config.ts frontend/tailwind.config.ts  # перезапишет
cp -r components/* frontend/components/ui/gsm/
```

### Шаг 3. Подключить в layout

`frontend/app/layout.tsx`:

```tsx
import { ThemeProvider, themeScript } from '@/components/ui/gsm/ThemeProvider';

export default function RootLayout({ children }) {
  return (
    <html lang="ru" data-theme="industrial-warm">
      <head>
        {/* Anti-FOUC: установить тему до гидрации */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
```

### Шаг 4. Обернуть dashboard-страницы в PageTransition

`frontend/app/dashboard/layout.tsx`:

```tsx
import { PageTransition } from '@/components/ui/gsm/PageTransition';

export default function DashboardLayout({ children }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar sections={NAV_SECTIONS} user={user} />
      <main className="flex-1 p-8">
        <PageTransition>{children}</PageTransition>
      </main>
    </div>
  );
}
```

### Шаг 5. Добавить ThemeSwitcher в шапку

```tsx
import { ThemeSwitcher } from '@/components/ui/gsm/ThemeSwitcher';

// где-то в header:
<div className="flex items-center gap-4">
  <ThemeSwitcher />
  {/* ... остальное */}
</div>
```

### Шаг 6. Добавить CommandPalette глобально

```tsx
import { CommandPalette, type Command } from '@/components/ui/gsm/CommandPalette';

const commands: Command[] = [
  {
    id: 'go-search',
    title: 'Подобрать масло',
    subtitle: 'Перейти к форме подбора',
    group: 'Действия',
    action: () => router.push('/dashboard/search'),
  },
  {
    id: 'go-imports',
    title: 'Загрузить каталог',
    subtitle: 'Импорт Excel в БД',
    group: 'Действия',
    action: () => router.push('/dashboard/imports'),
  },
  {
    id: 'theme-industrial',
    title: 'Industrial Warm',
    subtitle: 'Тёплая инженерная тема',
    group: 'Тема',
    action: () => setTheme('industrial-warm'),
  },
  // ... и так далее
];

export function AppShell({ children }) {
  return (
    <>
      {children}
      <CommandPalette commands={commands} />
    </>
  );
}
```

### Шаг 7. Заменить старые Dialog на новый

Старый `@base-ui/react/dialog` → новый `Dialog`:

```tsx
// Было:
import * as Dialog from '@base-ui/react/dialog';

// Стало:
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/gsm/Dialog';
```

API практически идентичный, но с spring-анимацией.

### Шаг 8. Использовать FluidCard в результатах поиска

`frontend/app/dashboard/search/page.tsx`:

```tsx
import { FluidCard, type RecommendationType } from '@/components/ui/gsm/FluidCard';

{results.map((fluid, i) => (
  <FluidCard
    key={fluid.id}
    index={i}
    brand={fluid.brand}
    name={fluid.name}
    type={fluid.is_oem ? 'oem' : fluid.has_approval ? 'approval' : 'alternative'}
    specs={[
      { label: fluid.viscosity_sae, kind: 'sae' },
      { label: fluid.api_class, kind: 'api' },
    ]}
    volume={`${fluid.volume_liters} L`}
    volumeWithFilter={`${fluid.volume_with_filter} L`}
    onClick={() => openFluidDetail(fluid.id)}
  />
))}
```

## 📐 Дизайн-принципы (важно соблюдать!)

### ❌ НЕ делать
- ❌ Glassmorphism (полупрозрачные карточки с blur) — убивает читаемость в B2B
- ❌ Радуга из 10 цветов для node_type — используем 5 групп
- ❌ Spring-анимации на ВСЕ модалки — только на critical interactions
- ❌ Ripple-эффекты на кнопках — устаревший Material Design 2014
- ❌ Больше 4-5 семантических цветов одновременно
- ❌ Pure black (`#000`) для dark mode — используем `oklch(0.14 0.005 250)`

### ✅ ДЕЛАТЬ
- ✅ Моноширинный шрифт для ВСЕХ технических данных (вязкости, артикулы, OEM-номера, объёмы, коды двигателей)
- ✅ Семантические бейджи: OEM=зелёный, допуск=синий, аналог=серый
- ✅ Цветовое кодирование по 5 группам узлов, не по 10 типам
- ✅ Микро-анимации 120-180ms с `cubic-bezier(0.16, 1, 0.3, 1)`
- ✅ `prefers-reduced-motion: reduce` — обязательно
- ✅ Comfortable density: padding 16-24px, font-size 14-15px
- ✅ `:focus-visible` (не `:focus`) — чтобы не было рамок при клике мышью

## 🎯 Цветовые токены — шпаргалка

| Токен | Использовать для |
|---|---|
| `--background` | Фон страницы |
| `--foreground` | Основной текст |
| `--surface-1` | Карточки |
| `--surface-2` | Hover, nested cards |
| `--primary` | Основные кнопки, ссылки, активные элементы |
| `--accent` | Вторичные акценты, sidebar-active |
| `--success` | OEM-оригинал, успешные статусы |
| `--info` | Допуски OEM, в работе |
| `--warning` | Grace period, внимание |
| `--destructive` | Удаление, ошибки |
| `--sidebar` | Тёмная боковая панель |
| `--sidebar-accent` | Активный пункт в sidebar |
| `--border` | Тонкие границы |
| `--border-strong` | Выделенные границы (table header) |

## 🔤 Типографика — шпаргалка

```tsx
// Заголовки
<h1 className="text-3xl font-semibold tracking-tight">Page title</h1>
<h2 className="text-xl font-semibold tracking-tight">Section title</h2>
<h3 className="text-base font-semibold tracking-tight">Card title</h3>

// Body
<p className="text-base">Обычный текст 15px — B2B sweet spot</p>
<p className="text-sm text-[var(--sidebar-muted)]">Secondary text 14px</p>
<p className="text-xs uppercase tracking-wide">LABEL 12px</p>

// Технические данные — ВСЕГДА моноширинные
<span className="font-mono text-sm">5W-30 · K20A · LA-CL7 · 4.2L</span>
```

## 🧪 Демо для инвесторов

`preview.html` — это **главный артефакт для показа инвесторам**.
Открывается двойным кликом в браузере, показывает:
- Все 3 темы с мгновенным переключением
- Реальные компоненты: FluidCard, Dialog, CommandPalette, Sales Copilot
- Реальные данные из последнего ETL-прогона (11 167 строк, 8 брендов, 538 моделей)
- Cmd+K палитру — нажмите Ctrl+K или ⌘K

## ⚠️ Известные ограничения

1. **Tailwind config требует пересборки** — после замены `tailwind.config.ts` нужно `npm run build` или restart dev-сервера
2. **Framer Motion добавит ~30 KB** в бандл — приемлемо для B2B
3. **Шрифты Inter + JetBrains Mono** грузятся с Google Fonts — для production рекомендуется self-host через `next/font`
4. **OKLCH поддерживается во всех современных браузерах** (Chrome 111+, Firefox 113+, Safari 15.4+). Для старых браузеров нужен fallback

## 🛣️ Roadmap (после интеграции)

- [ ] Demo-режим с моковыми данными для инвесторов (отдельный route `/demo`)
- [ ] Density toggle (Compact / Comfortable) — сохранить в localStorage
- [ ] Hot-reload тем через CSS variables — уже работает, нужно проверить в проде
- [ ] Self-host шрифтов через `next/font/google`
- [ ] A/B тестирование тем через PostHog
- [ ] Role-based темы (manager → light, technologist → dark, admin → system)

## 💬 Обратная связь

Если что-то не работает или выглядит не так — откройте `preview.html` в браузере и сравните с тем, что у вас в проекте. Демо — это source of truth.

Главный принцип: **тихая сложность, не громкая красота**. B2B-пользователь работает с интерфейсом 8 часов в день — он оценит скорость и ясность, а не анимации.
