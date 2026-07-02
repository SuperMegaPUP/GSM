'use client';

import { motion } from 'framer-motion';
import { Database, BookOpen, Upload, ArrowUpRight } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

const STATS = [
  { label: 'Автомобилей', value: '8 183' },
  { label: 'Брендов', value: '71' },
  { label: 'Рекомендаций', value: '24 038' },
  { label: 'Каталогов', value: '3' },
];

export function SidePanel() {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-5"
    >
      {/* Stats */}
      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-[var(--sidebar-muted)]">
            <Database className="h-4 w-4" />
            <span>Сводка</span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {STATS.map((st) => (
              <div key={st.label}>
                <div className="text-lg font-semibold font-mono tracking-tight text-[var(--foreground)]">
                  {st.value}
                </div>
                <div className="text-xs text-[var(--sidebar-muted)]">{st.label}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Architecture */}
      <Card>
        <CardContent className="p-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-[var(--sidebar-muted)]">
            <BookOpen className="h-4 w-4" />
            <span>Архитектура</span>
          </div>
          <div className="space-y-2 text-xs text-[var(--sidebar-muted)] leading-relaxed">
            <p className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--node-engine)]" />
              Двигатель / Охлаждение
            </p>
            <p className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--node-transmission)]" />
              Трансмиссия (АКПП, МКПП, Вариатор, Раздатка)
            </p>
            <p className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--node-drivetrain)]" />
              Привод (Передний/Задний мост)
            </p>
            <p className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--node-fluids)]" />
              Жидкости (ГУР, Охлаждение)
            </p>
            <p className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-[var(--node-brakes)]" />
              Тормозная система
            </p>
          </div>
          <div className="pt-1 text-[10px] text-[var(--sidebar-muted)] border-t border-dashed border-[var(--border)]">
            Подбор по уникальному коду комплектации
          </div>
        </CardContent>
      </Card>

      {/* Import CTA */}
      <Card className="border-dashed border-[var(--primary-muted)] bg-[var(--primary-muted)]/30">
        <CardContent className="p-5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-[var(--primary)]">
            <Upload className="h-4 w-4" />
            <span>Импорт каталога</span>
          </div>
          <p className="text-xs text-[var(--sidebar-muted)] leading-relaxed">
            Загрузите свой каталог масел в формате XLSX или CSV для автоматического подбора.
          </p>
          <button className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--primary)] hover:text-[var(--primary-hover)] transition-colors">
            Подробнее
            <ArrowUpRight className="h-3 w-3" />
          </button>
        </CardContent>
      </Card>
    </motion.div>
  );
}
