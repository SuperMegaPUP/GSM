'use client';

import { motion } from 'framer-motion';

export type VehicleType =
  | 'passenger_car'
  | 'heavy_truck'
  | 'heavy_equipment'
  | 'motorcycle'
  | 'small_engine';

const VEHICLE_TYPES: {
  value: VehicleType;
  label: string;
  icon: string; // SVG path data
  count?: string;
  disabled?: boolean;
}[] = [
  {
    value: 'passenger_car',
    label: 'Легковые',
    icon: 'M3 10l2-5h14l2 5M3 10v6a1 1 0 001 1h2a1 1 0 001-1v-1h10v1a1 1 0 001 1h2a1 1 0 001-1v-6M5 14a2 2 0 100-4 2 2 0 000 4zm14 0a2 2 0 100-4 2 2 0 000 4z',
    count: '2 920 авто',
  },
  {
    value: 'heavy_truck',
    label: 'Грузовые',
    icon: 'M3 15h3v-4H3v4zm3 0h12M6 15v2a1 1 0 001 1h2a1 1 0 001-1v-2h6v2a1 1 0 001 1h2a1 1 0 001-1v-2h1a1 1 0 001-1v-6l-3-4H9v10M7 18a2 2 0 100-4 2 2 0 000 4zm10 0a2 2 0 100-4 2 2 0 000 4z',
    count: 'скоро',
    disabled: true,
  },
  {
    value: 'heavy_equipment',
    label: 'Спецтехника',
    icon: 'M4 8h12v10H4V8zm0-2l2-3h10l2 3M6 18v2h8v-2M14 12h4v4h-4z',
    count: 'скоро',
    disabled: true,
  },
  {
    value: 'motorcycle',
    label: 'Мототехника',
    icon: 'M5 18a3 3 0 100-6 3 3 0 000 6zm14-6h-4l-3-4h-3M5 12h14M18 18a3 3 0 100-6 3 3 0 000 6z',
    count: 'скоро',
    disabled: true,
  },
  {
    value: 'small_engine',
    label: 'Бензопилы / Косилки',
    icon: 'M7 10h10v8H7v-8zm2-4h6l1 4H8l1-4zm7 12v2H8v-2',
    count: 'скоро',
    disabled: true,
  },
];

interface VehicleTypeTabsProps {
  value: VehicleType;
  onChange: (value: VehicleType) => void;
}

export function VehicleTypeTabs({ value, onChange }: VehicleTypeTabsProps) {
  return (
    <div className="vehicle-tabs">
      {VEHICLE_TYPES.map((vt) => {
        const isActive = vt.value === value;
        return (
          <button
            key={vt.value}
            type="button"
            disabled={vt.disabled}
            onClick={() => onChange(vt.value)}
            className={`vehicle-tab ${isActive ? 'vehicle-tab--active' : ''}`}
            aria-pressed={isActive}
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="vehicle-tab-icon"
            >
              <path d={vt.icon} />
            </svg>
            <span className="vehicle-tab-label">{vt.label}</span>
            {vt.count && (
              <span className={`vehicle-tab-count ${vt.disabled ? 'vehicle-tab-count--soon' : ''}`}>
                {vt.count}
              </span>
            )}
            {isActive && (
              <motion.div
                layoutId="vehicle-tab-indicator"
                className="vehicle-tab-indicator"
                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
