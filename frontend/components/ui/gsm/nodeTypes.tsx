export type NodeType =
  | 'ENGINE'
  | 'MANUAL_TRANSMISSION'
  | 'AUTO_TRANSMISSION'
  | 'CVT'
  | 'TRANSFER_CASE'
  | 'FRONT_DIFF'
  | 'REAR_DIFF'
  | 'STEERING'
  | 'BRAKE'
  | 'COOLANT'
  | 'SUSPENSION';

export type NodeGroup = 'engine' | 'transmission' | 'drivetrain' | 'fluids' | 'brakes' | 'hydraulic' | 'other';

interface NodeConfig {
  group: NodeGroup;
  pillClass: string;
  shortLabel: string;
  icon: string;
}

export const NODE_CONFIG: Record<NodeType, NodeConfig> = {
  ENGINE: {
    group: 'engine',
    pillClass: 'node-pill--engine',
    shortLabel: 'Двигатель',
    icon: 'M14 4h-4v4h-2v3H5v3h2v3h2v3h4M14 4v3h2v3h2v3h-2v3h-2v4',
  },
  COOLANT: {
    group: 'fluids',
    pillClass: 'node-pill--fluids',
    shortLabel: 'Охлаждение',
    icon: 'M12 2v6M12 22v-6M2 12h6M22 12h-6',
  },
  MANUAL_TRANSMISSION: {
    group: 'transmission',
    pillClass: 'node-pill--transmission',
    shortLabel: 'МКПП',
    icon: 'M12 2v3M12 19v3M22 12h-3M5 12H2M19 5l-2 2M7 17l-2 2M19 19l-2-2M7 7L5 5',
  },
  AUTO_TRANSMISSION: {
    group: 'transmission',
    pillClass: 'node-pill--transmission',
    shortLabel: 'АКПП',
    icon: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 9a3 3 0 100 6 3 3 0 000-6z',
  },
  CVT: {
    group: 'transmission',
    pillClass: 'node-pill--transmission',
    shortLabel: 'Вариатор',
    icon: 'M3 12c0-4 4-8 9-8s9 4 9 8-4 8-9 8-9-4-9-8zM8 12c0-2 2-4 4-4s4 2 4 4-2 4-4 4-4-2-4-4z',
  },
  TRANSFER_CASE: {
    group: 'transmission',
    pillClass: 'node-pill--transmission',
    shortLabel: 'Раздатка',
    icon: 'M2 12h4M18 12h4M12 2v4M12 18v4M5 5l3 3M16 16l3 3M5 19l3-3M16 8l3-3',
  },
  FRONT_DIFF: {
    group: 'drivetrain',
    pillClass: 'node-pill--drivetrain',
    shortLabel: 'Передний мост',
    icon: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 7v10M7 12h10',
  },
  REAR_DIFF: {
    group: 'drivetrain',
    pillClass: 'node-pill--drivetrain',
    shortLabel: 'Задний мост',
    icon: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 7a5 5 0 100 10 5 5 0 000-10z',
  },
  STEERING: {
    group: 'hydraulic',
    pillClass: 'node-pill--hydraulic',
    shortLabel: 'ГУР',
    icon: 'M12 2v6M12 22v-6M3 12h6M15 12h6',
  },
  BRAKE: {
    group: 'brakes',
    pillClass: 'node-pill--brakes',
    shortLabel: 'Тормоза',
    icon: 'M12 3a9 9 0 100 18 9 9 0 000-18zM12 9a3 3 0 100 6 3 3 0 000-6z',
  },
  SUSPENSION: {
    group: 'other',
    pillClass: 'node-pill--other',
    shortLabel: 'Подвеска',
    icon: 'M5 21V7l8-4v18M19 21V11l-6-4',
  },
};

export function NodeIcon({
  type,
  size = 12,
}: {
  type: NodeType;
  size?: number;
}) {
  const cfg = NODE_CONFIG[type];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ opacity: 0.9 }}
    >
      <path d={cfg.icon} />
    </svg>
  );
}
