'use client';

import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

const RANK_CONFIG: Record<number, { label: string; cssClass: string }> = {
  1: { label: 'Основное', cssClass: 'fluid-card--rank-1' },
  2: { label: 'Alt 1', cssClass: 'fluid-card--rank-2' },
  3: { label: 'Alt 2', cssClass: 'fluid-card--rank-3' },
};

function rankClass(rank: number): string {
  const cfg = RANK_CONFIG[rank];
  if (cfg) return cfg.cssClass;
  return 'fluid-card--rank-n';
}

function rankLabel(rank: number): string {
  const cfg = RANK_CONFIG[rank];
  if (cfg) return cfg.label;
  return `Сноска (${rank})`;
}

interface FluidCardProps {
  brand: string;
  name: string;
  recommendationRank: number;
  specs: { label: string; kind?: 'sae' | 'api' | 'default' }[];
  conditions?: string[];
  volume?: string;
  volumeWithFilter?: string;
  extra?: ReactNode;
  onClick?: () => void;
  index?: number;
}

export function FluidCard({
  brand,
  name,
  recommendationRank,
  specs,
  conditions,
  volume,
  volumeWithFilter,
  extra,
  onClick,
  index = 0,
}: FluidCardProps) {
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
      className={`fluid-card cursor-pointer ${rankClass(recommendationRank)}`}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-[var(--sidebar-muted)]">
            {brand}
          </div>
          <h3 className="text-base font-semibold tracking-tight truncate">{name}</h3>
        </div>
        <span className={`rank-badge ${rankClass(recommendationRank)}`}>
          {recommendationRank === 1 && <span className="rank-badge-star">★</span>}
          {rankLabel(recommendationRank)}
        </span>
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

      {conditions && conditions.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {conditions.map((cond, i) => (
            <span key={i} className="condition-chip">{cond}</span>
          ))}
        </div>
      )}

      {(volume || volumeWithFilter) && (
        <div className="border-t border-dashed border-[var(--border)] pt-3 font-mono text-sm font-medium">
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
