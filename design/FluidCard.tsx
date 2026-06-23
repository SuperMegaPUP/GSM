'use client';

/**
 * GSM Design System — FluidCard
 *
 * The core card for displaying oil/fluid recommendation in search results.
 * Visual cues:
 *   - Left border color encodes recommendation type (OEM/approval/alternative)
 *   - Spec pills use mono font for technical credibility
 *   - Hover lifts card and emphasizes border
 */

import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

export type RecommendationType = 'oem' | 'approval' | 'alternative';

interface FluidCardProps {
  brand: string;
  name: string;
  type: RecommendationType;
  specs: { label: string; kind?: 'sae' | 'api' | 'default' }[];
  volume?: string;
  volumeWithFilter?: string;
  extra?: ReactNode;
  onClick?: () => void;
  index?: number;
}

const TYPE_CONFIG: Record<
  RecommendationType,
  { badgeClass: string; badgeText: string; borderColor: string }
> = {
  oem: {
    badgeClass: 'badge-oem',
    badgeText: 'Оригинал',
    borderColor: 'var(--success)',
  },
  approval: {
    badgeClass: 'badge-approval',
    badgeText: 'Допуск OEM',
    borderColor: 'var(--info)',
  },
  alternative: {
    badgeClass: 'badge-alternative',
    badgeText: 'Аналог',
    borderColor: 'var(--sidebar-muted)',
  },
};

export function FluidCard({
  brand,
  name,
  type,
  specs,
  volume,
  volumeWithFilter,
  extra,
  onClick,
  index = 0,
}: FluidCardProps) {
  const cfg = TYPE_CONFIG[type];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.24,
        delay: Math.min(index * 0.03, 0.3),
        ease: [0.16, 1, 0.3, 1],
      }}
      onClick={onClick}
      className="fluid-card cursor-pointer"
      style={{ '--badge-color': cfg.borderColor } as React.CSSProperties}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--sidebar-muted)]">
            {brand}
          </div>
          <h3 className="text-base font-semibold tracking-tight">{name}</h3>
        </div>
        <span className={`badge ${cfg.badgeClass}`}>{cfg.badgeText}</span>
      </div>

      <div className="mb-3 flex flex-wrap gap-1.5">
        {specs.map((spec, i) => (
          <span
            key={i}
            className={`spec-pill ${
              spec.kind === 'sae'
                ? 'spec-pill-sae'
                : spec.kind === 'api'
                ? 'spec-pill-api'
                : ''
            }`}
          >
            {spec.label}
          </span>
        ))}
      </div>

      {(volume || volumeWithFilter) && (
        <div className="mt-2 border-t border-dashed border-[var(--border)] pt-3 font-mono text-sm font-medium">
          {volume && (
            <>
              <span className="mr-2 font-sans font-normal text-[var(--sidebar-muted)]">
                Объём:
              </span>
              {volume}
            </>
          )}
          {volumeWithFilter && (
            <>
              <span className="ml-4 mr-2 font-sans font-normal text-[var(--sidebar-muted)]">
                с фильтром:
              </span>
              {volumeWithFilter}
            </>
          )}
        </div>
      )}

      {extra && <div className="mt-3">{extra}</div>}
    </motion.div>
  );
}
