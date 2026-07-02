╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ЕДИНЫЙ ПРОМПТ ДЛЯ ЛОКАЛЬНОЙ LLM-КОДЕРА — ВЕРСИЯ 3.2 (ФИНАЛЬНАЯ)            ║
║   ИМПОРТ PVL-КАТАЛОГА В СУЩЕСТВУЮЩУЮ БД GSM                                  ║
║                                                                              ║
║   Версия: 3.2 FINAL | Дата: 2026-07-02                                       ║
║   Стек: FastAPI + SQLAlchemy 2.0 async + Next.js 14 + Qdrant                 ║
║                                                                              ║
║   ИСПРАВЛЕНИЯ vs v3.1:                                                       ║
║   1. CAST(:node AS node_type) вместо :node::node_type (asyncpg не переваривает)║
║   2. volume_liters — numeric(5,2), парсим первое число, raw в conditions   ║
║   3. import re в начале модуля (без __import__('re'))                       ║
║   4. DROP INDEX IF EXISTS вместо динамического поиска constraint            ║
║   5. detect() + parse() — один read_excel, не два                            ║
║                                                                              ║
║   ИСПРАВЛЕНИЯ vs v3.0 (сохранены):                                           ║
║   1. tenant_id → company_id (везде)                                          ║
║   2. name → name_ru, displacement_liters → engine_volume,                    ║
║      body_number → body_type                                                 ║
║   3. FluidType enum: engine_oil, manual_transmission, auto_transmission,     ║
║      cvt, differential, transfer_case, steering, brake, coolant              ║
║   4. DIFFERENTIAL → FRONT_DIFF (default), REAR_DIFF (из сносок)              ║
║   5. UNIQUE constraint: (company_id, car_variant_id, node_type,              ║
║      recommendation_rank)                                                    ║
║   6. car_models UNIQUE: (brand_id, name, generation, company_id)             ║
║   7. SUSPENSION добавлен в node_type и fluid_type enum                       ║
║   8. Все SQL-запросы переписаны под реальные имена колонок                   ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

═══════════════════════════════════════════════════════════════════════════════
0. ВАЖНОЕ ПРЕДИСЛОВИЕ
═══════════════════════════════════════════════════════════════════════════════

Этот промпт — исправленная версия v3.0 с учётом реальной кодовой базы.

❌ НЕ создавай новые таблицы vehicles / vehicle_recommendations / vehicle_nodes.
✅ РАСШИРЬ существующие таблицы: car_brands, car_variants, recommendations.
✅ Переиспользуй существующий конвейер process_import_batch() + index_qdrant_task().
✅ Создай новый парсер parse_pvl_catalog() рядом с parse_japanese_catalog().
✅ ИСПОЛЬЗУЙ ТОЛЬКО РЕАЛЬНЫЕ ИМЕНА КОЛОНОК (см. шаг 4 — Inventory).

Все исходники-референсы уже скопированы в:
  /home/g/gsm/vehicle-architecture/

Используй их как РЕФЕРЕНС логики парсинга, но НЕ копируй SQL/Python дословно —
адаптируй под реальные имена колонок и существующий enum.

═══════════════════════════════════════════════════════════════════════════════
1. КОНТЕКСТ ПРОЕКТА
═══════════════════════════════════════════════════════════════════════════════

GSM — B2B SaaS для продавцов моторных масел. Менеджер вводит марку/модель/год
авто — система подбирает масла для двигателя, КПП, дифференциалов и т.д.

ТЕКУЩЕЕ СОСТОЯНИЕ:
  - 8 брендов JDM (Honda, Toyota, Nissan, Mazda, Mitsubishi, Subaru, Suzuki, Daihatsu)
  - 378 моделей, 2 236 вариантов, 270 жидкостей
  - 11 167 рекомендаций в БД
  - 11 167 точек в Qdrant
  - Рабочий конвейер импорта: process_import_batch() + Celery task
  - Рабочий UI поиска с группировкой по node_type

ЗАДАЧА: добавить каталог PVL (Газпромнефть) — 36 брендов, 2 929 авто, 21 762
рекомендации. После импорта суммарно: 62 бренда, ~5 165 вариантов, ~32 929
рекомендаций.

═══════════════════════════════════════════════════════════════════════════════
2. РЕАЛЬНАЯ СТРУКТУРА БД — INVENTORY (КРИТИЧНО!)
═══════════════════════════════════════════════════════════════════════════════

Перед началом работы ВЫПОЛНИ эти команды и СВЕРЬСЯ с реальной схемой:

  psql -d gsm -c "\d car_brands"
  psql -d gsm -c "\d car_models"
  psql -d gsm -c "\d car_variants"
  psql -d gsm -c "\d fluids"
  psql -d gsm -c "\d recommendations"
  psql -d gsm -c "\dT+"  # показать все типы, включая enum
  psql -d gsm -c "SELECT enum_range(NULL::node_type);"
  psql -d gsm -c "SELECT enum_range(NULL::fluid_type);"

2.1. car_brands — РЕАЛЬНЫЕ КОЛОНКИ:
  - id (uuid, PK)
  - company_id (uuid, NOT NULL)  ← НЕ tenant_id
  - name_ru (varchar)            ← НЕ name
  - name_en (varchar, nullable)
  - country (varchar, nullable)
  - created_at, updated_at

2.2. car_models — РЕАЛЬНЫЕ КОЛОНКИ + CONSTRAINT:
  - id (uuid, PK)
  - company_id (uuid, NOT NULL)
  - brand_id (uuid, FK → car_brands.id)
  - name (varchar)
  - generation (varchar, nullable)
  - created_at, updated_at
  - UNIQUE (brand_id, name, generation, company_id)  ← порядок важен!

2.3. car_variants — РЕАЛЬНЫЕ КОЛОНКИ:
  - id (uuid, PK)
  - company_id (uuid, NOT NULL)
  - model_id (uuid, FK → car_models.id)
  - body_type (varchar(50))         ← НЕ body_number
  - year_start (integer)
  - year_end (integer)
  - engine_code (varchar)
  - engine_volume (numeric(3,1))    ← НЕ displacement_liters; вмещает 0.0–99.9
  - fuel_type (varchar)
  - drive_type (varchar)
  - transmission_type (varchar)
  - source_hash (varchar)
  - created_at, updated_at
  - UNIQUE (company_id, source_hash)

2.4. fluids — РЕАЛЬНЫЕ КОЛОНКИ:
  - id (uuid, PK)
  - company_id (uuid, NOT NULL)
  - canonical_name (varchar)
  - brand (varchar)
  - product_line (varchar)
  - viscosity_sae (varchar)
  - api_class (varchar)
  - oem_approvals (jsonb)
  - fluid_type (fluid_type enum)   ← см. enum ниже
  - hash_signature (varchar)
  - created_at, updated_at

2.5. recommendations — РЕАЛЬНЫЕ КОЛОНКИ + CONSTRAINT:
  - id (uuid, PK)
  - company_id (uuid, NOT NULL)
  - car_variant_id (uuid, FK → car_variants.id)
  - node_type (node_type enum)
  - fluid_id (uuid, FK → fluids.id)
  - volume_liters (varchar)
  - volume_with_filter (varchar)
  - is_oem_recommendation (boolean)
  - oem_specification (varchar)
  - source (varchar)
  - created_at, updated_at
  - UNIQUE (company_id, car_variant_id, node_type, fluid_id)  ← СТАРЫЙ

2.6. РЕАЛЬНЫЕ ENUM'Ы:

  node_type:
    ENGINE, MANUAL_TRANSMISSION, AUTO_TRANSMISSION, CVT,
    TRANSFER_CASE, FRONT_DIFF, REAR_DIFF, STEERING, BRAKE, COOLANT

  fluid_type (ВНИМАНИЕ — нестандартное именование!):
    engine_oil, manual_transmission, auto_transmission, cvt,
    differential, transfer_case, steering, brake, coolant

  ⚠️ ВАЖНО: fluid_type в этом проекте семантически означает
     "система/узел, для которой эта жидкость предназначена",
     а не тип самой жидкости. Это странно, но так сделано —
     не пытайся "исправить" это, просто маппь PVL-системы на
     существующие значения fluid_type.

═══════════════════════════════════════════════════════════════════════════════
3. ФИНАЛЬНАЯ АРХИТЕКТУРА (УТВЕРЖДЕНА)
═══════════════════════════════════════════════════════════════════════════════

Принципы:
  1. НЕ создаём новые таблицы — расширяем существующие
  2. Переиспользуем process_import_batch() + index_qdrant_task()
  3. Создаём новый парсер parse_pvl_catalog()
  4. Сохраняем ВСЕ данные из PVL (Diesel-секции + сноски + 3 ранга масел)
  5. Используем ТОЛЬКО РЕАЛЬНЫЕ имена колонок (см. шаг 2)

КАК PVL ДАННЫЕ ЛОЖАТСЯ В СУЩЕСТВУЮЩИЕ ТАБЛИЦЫ:

  car_brands:
    - company_id = текущая компания
    - name_ru = "Audi" (нормализованное)
    - name_en = NULL (в PVL нет английских названий)
    - country = NULL (в PVL не указано)
    + НОВОЕ ПОЛЕ: vehicle_type = "passenger_car"
    + НОВОЕ ПОЛЕ: market = "EU" / "US" / "RU"

  car_models:
    - company_id, brand_id
    - name = "A1" (префикс до первой цифры)
    - generation = "W168" / "E46" / NULL (если не указано в PVL)

  car_variants:
    - company_id, model_id
    - body_type = NULL (в PVL нет кодов кузова)       ← НЕ body_number!
    - year_start = 2010 (из '10-)
    - year_end = NULL (если '10- значит до настоящего)
    - engine_code = NULL (в PVL нет кодов двигателя)
    - engine_volume = 1.2 (numeric(3,1), извлечено из названия "A1 1.2 TFSI")
    - fuel_type = "petrol" / "diesel"
    - drive_type = NULL
    - transmission_type = NULL
    - source_hash = SHA-256(pvl|brand|model|generation|sub_model|years)
    + НОВОЕ ПОЛЕ: sub_model = "1.2 TFSI" / "Diesel 1.9 TDI"
    + НОВОЕ ПОЛЕ: market = "EU" / "US" / "RU"
    + НОВОЕ ПОЛЕ: attributes = JSONB (engine_oil_volume_raw, pvl_marker)

  fluids:
    - company_id
    - canonical_name = "G-Energy F Synth 5W-40"
    - brand = "G-Energy" (извлечено из названия)
    - product_line = "F Synth" (часть названия после бренда)
    - viscosity_sae = "5W-40"
    - api_class = NULL
    - fluid_type = СМ. МАППИНГ НИЖЕ (engine_oil / manual_transmission / ...)
    - hash_signature = SHA-256(canonical_name)[:16]

  recommendations:
    - company_id, car_variant_id, fluid_id
    - node_type = ENGINE / MANUAL_TRANSMISSION / AUTO_TRANSMISSION /
                  FRONT_DIFF / REAR_DIFF / TRANSFER_CASE / CVT /
                  COOLANT / BRAKE / STEERING / SUSPENSION (НОВОЕ)
    - volume_liters = NUMERIC(5,2)  ← НЕ VARCHAR!
      ВАЖНО: PVL содержит диапазоны ("0.8-1.2", "<") и спецсимволы.
      Решение (Вариант А + Б):
        • volume_liters = первое распарсенное число (numeric(5,2))
          "2,1" → 2.10, "1,9-2,4" → 1.90, "<" → NULL, "-" → NULL
        • applicability_conditions.volume_raw = исходная строка ("1,9-2,4")
          для отображения пользователю полного диапазона
    - is_oem_recommendation = true (для rank=1) / false (для rank 2+)
    - source = "pvl"
    + НОВОЕ ПОЛЕ: recommendation_rank = 1 / 2 / 3 / 4+
    + НОВОЕ ПОЛЕ: applicability_conditions = JSONB (включает volume_raw)
    + НОВОЕ ПОЛЕ: fluid_name_override = "G-Energy F Synth 5W-40" (если fluid_id NULL)
    + ИЗМЕНЁННЫЙ CONSTRAINT: UNIQUE (company_id, car_variant_id, node_type,
                                      recommendation_rank)

═══════════════════════════════════════════════════════════════════════════════
4. МАППИНГ PVL → СУЩЕСТВУЮЩИЕ ENUM'Ы (КРИТИЧНО!)
═══════════════════════════════════════════════════════════════════════════════

4.1. PVL-система → node_type + fluid_type (используй ОБА значения):

  | PVL система              | node_type            | fluid_type            |
  |--------------------------|----------------------|-----------------------|
  | Двигатель (cols 3-7)     | ENGINE               | engine_oil            |
  | Ручная трансмиссия (8-10)| MANUAL_TRANSMISSION  | manual_transmission   |
  | АКПП (cols 11-14)        | AUTO_TRANSMISSION    | auto_transmission     |
  | Дифференциал (cols 15-18)| FRONT_DIFF           | differential          |
  | Охлаждение (cols 19-21)  | COOLANT              | coolant               |
  | Тормоза (cols 22-24)     | BRAKE                | brake                 |
  | ГУР (cols 25-27)         | STEERING             | steering              |
  | Подвеска (cols 28-30)    | SUSPENSION (НОВОЕ)   | suspension (НОВОЕ)    |

4.2. PVL-сноска → node_type (по ключевым словам в тексте сноски):

  | Ключевые слова в сноске        | node_type        |
  |--------------------------------|------------------|
  | "задний дифференциал"          | REAR_DIFF        |
  | "передний дифференциал"        | FRONT_DIFF       |
  | "самоблокирующийся дифференциал"| REAR_DIFF       |
  | "передний и задний дифференциалы"| FRONT_DIFF + conditions={"also_rear": true} |
  | "дифференциал" (без уточнения) | FRONT_DIFF       |
  | "раздаточная коробка"          | TRANSFER_CASE    |
  | "сцепление Haldex"             | TRANSFER_CASE    |
  | "вариатор"                     | CVT              |
  | "автоматическая коробка"       | AUTO_TRANSMISSION|
  | "коробка передач"              | MANUAL_TRANSMISSION |
  | "гидравлическая система"       | STEERING         |

4.3. Маркеры комплектации PVL (col 6, 10, 13, 17):
  Символы 'u', 'a', 'c', 'd', 'e', 'f', 'g', 'h', 'j', 'k', 'l', 'm',
  'n', 'o', 'p', 'q', 'r', 's', 't', 'ar', 'af', 'df', 'gh' и т.д.
  Сохраняй как applicability_conditions.marker_code = "u"

═══════════════════════════════════════════════════════════════════════════════
5. МИГРАЦИЯ БД (ТОЧНАЯ КОПИЯ ДЛЯ ВЫПОЛНЕНИЯ)
═══════════════════════════════════════════════════════════════════════════════

Создай Alembic миграцию или выполни прямой SQL:

-- ============================================================================
-- Migration: add PVL support fields (v2 — corrected)
-- ============================================================================

-- 1. Добавить SUSPENSION в node_type enum
DO $$ BEGIN
    ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'SUSPENSION';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- 2. Добавить suspension в fluid_type enum (для согласованности)
DO $$ BEGIN
    ALTER TYPE fluid_type ADD VALUE IF NOT EXISTS 'suspension';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- 3. car_brands: добавить vehicle_type и market
ALTER TABLE car_brands ADD COLUMN IF NOT EXISTS vehicle_type VARCHAR(30)
    NOT NULL DEFAULT 'passenger_car';
ALTER TABLE car_brands ADD COLUMN IF NOT EXISTS market VARCHAR(20);

CREATE INDEX IF NOT EXISTS idx_car_brands_vehicle_type
    ON car_brands (vehicle_type);

-- 4. car_variants: добавить sub_model, market, attributes
ALTER TABLE car_variants ADD COLUMN IF NOT EXISTS sub_model VARCHAR(200);
ALTER TABLE car_variants ADD COLUMN IF NOT EXISTS market VARCHAR(20);
ALTER TABLE car_variants ADD COLUMN IF NOT EXISTS attributes JSONB DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_car_variants_sub_model
    ON car_variants (sub_model);
CREATE INDEX IF NOT EXISTS idx_car_variants_market
    ON car_variants (market);
CREATE INDEX IF NOT EXISTS idx_car_variants_attributes_gin
    ON car_variants USING gin (attributes jsonb_path_ops);

-- 5. recommendations: добавить recommendation_rank, applicability_conditions, fluid_name_override
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS recommendation_rank SMALLINT
    NOT NULL DEFAULT 1;
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS applicability_conditions JSONB
    DEFAULT '{}'::jsonb;
ALTER TABLE recommendations ADD COLUMN IF NOT EXISTS fluid_name_override VARCHAR(300);

-- Обновить существующие рекомендации: rank=1 (они все были primary в старом каталоге)
UPDATE recommendations SET recommendation_rank = 1 WHERE recommendation_rank IS NULL;

-- 6. ИЗМЕНИТЬ UNIQUE INDEX (а не constraint!)
-- ВНИМАНИЕ: в реальной БД это UNIQUE INDEX uq_recommendations_variant_node_fluid,
-- а не table constraint. Динамический поиск по ordinal positions ненадёжен —
-- используем прямые имена. Перед выполнением СВЕРЬСЯ через:
--   \di recommendations
--   \d recommendations
-- Если имя индекса отличается — подставь реальное имя в DROP INDEX.

-- Сначала проверь, есть ли старый UNIQUE INDEX:
-- psql -c "\di recommendations" | grep uq_recommendations

-- Дропаем старый UNIQUE INDEX (если существует с таким именем):
DROP INDEX IF EXISTS uq_recommendations_variant_node_fluid;
-- Альтернативные возможные имена (если твой проект использует другое):
DROP INDEX IF EXISTS recommendations_car_variant_id_node_type_fluid_id_key;
DROP INDEX IF EXISTS recommendations_unique;

-- Создаём НОВЫЙ UNIQUE INDEX с recommendation_rank:
CREATE UNIQUE INDEX IF NOT EXISTS uq_recommendations_variant_node_rank
    ON recommendations (company_id, car_variant_id, node_type, recommendation_rank);

CREATE INDEX IF NOT EXISTS idx_recommendations_rank
    ON recommendations (company_id, car_variant_id, node_type, recommendation_rank);
CREATE INDEX IF NOT EXISTS idx_recommendations_conditions_gin
    ON recommendations USING gin (applicability_conditions jsonb_path_ops);

-- 7. Обновить существующие JDM-бренды: vehicle_type='passenger_car', market='JDM'
UPDATE car_brands
SET vehicle_type = 'passenger_car',
    market = COALESCE(market, 'JDM')
WHERE vehicle_type IS NULL OR vehicle_type = '';

-- 8. Комментарии к схеме
COMMENT ON COLUMN car_brands.vehicle_type IS 'Тип техники: passenger_car, heavy_truck, heavy_equipment, motorcycle, small_engine';
COMMENT ON COLUMN car_brands.market IS 'Рынок: JDM, EU, US, RU, CN';
COMMENT ON COLUMN car_variants.sub_model IS 'Модификация: 1.2 TFSI, 1.9 TDI, Diesel, Quattro';
COMMENT ON COLUMN car_variants.attributes IS 'Гибкие type-specific атрибуты (engine_oil_volume_raw, pvl_marker)';
COMMENT ON COLUMN recommendations.recommendation_rank IS '1=primary, 2=alt1, 3=alt2, 4+=footnote';
COMMENT ON COLUMN recommendations.applicability_conditions IS 'Условия: marker_code, fuel_type, has_ac, also_rear';
COMMENT ON COLUMN recommendations.fluid_name_override IS 'Имя масла, если fluid_id NULL';

-- ============================================================================

ПРОВЕРКА ПОСЛЕ МИГРАЦИИ:

  psql -d gsm -c "\d car_brands"          | должно содержать: vehicle_type, market
  psql -d gsm -c "\d car_variants"        | должно содержать: sub_model, market, attributes
  psql -d gsm -c "\d recommendations"     | должно содержать: recommendation_rank, applicability_conditions, fluid_name_override
  psql -d gsm -c "SELECT enum_range(NULL::node_type);"   | должно включать SUSPENSION
  psql -d gsm -c "SELECT enum_range(NULL::fluid_type);"  | должно включать suspension
  psql -d gsm -c "\d recommendations" | grep -i unique   | constraint recommendations_unique_rank (company_id, car_variant_id, node_type, recommendation_rank)

═══════════════════════════════════════════════════════════════════════════════
6. PVL-ПАРСЕР — ТОЧНАЯ СПЕЦИФИКАЦИЯ
═══════════════════════════════════════════════════════════════════════════════

Создай файл backend/app/services/pvl_parser.py:

```python
"""
GSM PVL Catalog Parser
=======================

Парсер для "Каталог подбора PVL.xlsx" (Газпромнефть).

ВАЖНО: ИСПОЛЬЗУЙ РЕАЛЬНЫЕ ИМЕНА КОЛОНОК:
  - company_id (НЕ tenant_id)
  - car_brands.name_ru (НЕ name)
  - car_variants.engine_volume (НЕ displacement_liters)
  - car_variants.body_type (НЕ body_number)
  - fluid_type enum: engine_oil, manual_transmission, auto_transmission,
                     cvt, differential, transfer_case, steering, brake,
                     coolant, suspension
  - node_type enum: ENGINE, MANUAL_TRANSMISSION, AUTO_TRANSMISSION, CVT,
                    TRANSFER_CASE, FRONT_DIFF, REAR_DIFF, STEERING, BRAKE,
                    COOLANT, SUSPENSION
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# МАППИНГ PVL → СУЩЕСТВУЮЩИЕ ENUM (КРИТИЧНО!)
# ============================================================================

# PVL-система → (node_type, fluid_type)
PVL_NODE_MAP = {
    'ENGINE':              ('ENGINE',              'engine_oil'),
    'MANUAL_TRANSMISSION': ('MANUAL_TRANSMISSION', 'manual_transmission'),
    'AUTO_TRANSMISSION':   ('AUTO_TRANSMISSION',   'auto_transmission'),
    'DIFFERENTIAL':        ('FRONT_DIFF',          'differential'),
    'COOLANT':             ('COOLANT',             'coolant'),
    'BRAKE':               ('BRAKE',               'brake'),
    'STEERING':            ('STEERING',            'steering'),
    'SUSPENSION':          ('SUSPENSION',          'suspension'),
}

# PVL-сноска → node_type (по ключевым словам в тексте)
FOOTNOTE_NODE_MAP = [
    (r'задн[ийе]+\s+дифференциал', 'REAR_DIFF'),
    (r'передн[ийе]+\s+дифференциал', 'FRONT_DIFF'),
    (r'самоблокирующийся\s+дифференциал', 'REAR_DIFF'),
    (r'передний\s+и\s+задний', 'FRONT_DIFF'),  # оба — помечаем в conditions
    (r'дифференциал', 'FRONT_DIFF'),
    (r'раздаточн', 'TRANSFER_CASE'),
    (r'сцепление\s+haldex', 'TRANSFER_CASE'),
    (r'вариатор', 'CVT'),
    (r'автоматическ', 'AUTO_TRANSMISSION'),
    (r'коробк[ау]\s+передач', 'MANUAL_TRANSMISSION'),
    (r'гидравлическ', 'STEERING'),
]

# Соответствие node_type → fluid_type (для случаев, когда сноска задаёт node_type)
NODE_TO_FLUID_TYPE = {
    'ENGINE': 'engine_oil',
    'MANUAL_TRANSMISSION': 'manual_transmission',
    'AUTO_TRANSMISSION': 'auto_transmission',
    'CVT': 'cvt',
    'FRONT_DIFF': 'differential',
    'REAR_DIFF': 'differential',
    'TRANSFER_CASE': 'transfer_case',
    'STEERING': 'steering',
    'BRAKE': 'brake',
    'COOLANT': 'coolant',
    'SUSPENSION': 'suspension',
}


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class PVLFluidRecommendation:
    """Одна рекомендация масла для одного узла."""
    node_type: str                # ENGINE, MANUAL_TRANSMISSION, FRONT_DIFF, etc.
    fluid_type: str               # engine_oil, manual_transmission, differential, etc.
    fluid_name: str               # "G-Energy F Synth 5W-40"
    fluid_brand: Optional[str] = None
    viscosity_sae: Optional[str] = None
    recommendation_rank: int = 1  # 1=primary, 2=alt1, 3=alt2, 4+=footnote
    is_oem: bool = False
    volume_liters: Optional[float] = None   # NUMERIC(5,2) — парсенное число
    applicability_conditions: dict = field(default_factory=dict)
    # applicability_conditions.volume_raw = "1,9-2,4" — исходная строка из PVL


@dataclass
class PVLVehicleRecord:
    """Распарсенная запись о ТС."""
    brand: str                    # "Audi"
    model: str                    # "A1" (префикс до первой цифры)
    model_full: str               # "A1 1.2 TFSI"
    generation: Optional[str] = None  # "W168", "E46"
    sub_model: Optional[str] = None   # "1.2 TFSI", "Diesel 1.9 TDI"
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    market: Optional[str] = None  # EU, US, RU
    engine_volume: Optional[float] = None  # 1.2 (numeric(3,1))
    fuel_type: str = "petrol"
    engine_oil_volume_raw: Optional[str] = None  # "3,5/4,5"
    recommendations: list[PVLFluidRecommendation] = field(default_factory=list)
    row_number: int = 0

    def source_hash(self) -> str:
        """Стабильный хэш для дедупликации."""
        key = f"pvl|{self.brand}|{self.model}|{self.generation or ''}|{self.sub_model or ''}|{self.year_start or ''}|{self.year_end or ''}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]


# ============================================================================
# PVL Parser
# ============================================================================

class PVLParser:
    """Парсер PVL-каталога."""

    # Соответствие колонок PVL → узлы
    NODE_COLUMNS = {
        'ENGINE':              {'main': 3,  'alt1': 4,  'alt2': 5,  'volume': 7,  'marker': 6},
        'MANUAL_TRANSMISSION': {'main': 8,  'alt1': 9,  'alt2': None, 'volume': None, 'marker': 10},
        'AUTO_TRANSMISSION':   {'main': 11, 'alt1': 12, 'alt2': None, 'volume': 14, 'marker': 13},
        'DIFFERENTIAL':        {'main': 15, 'alt1': 16, 'alt2': None, 'volume': 18, 'marker': 17},
        'COOLANT':             {'main': 19, 'alt1': 20, 'alt2': None, 'volume': 21, 'marker': None},
        'BRAKE':               {'main': 22, 'alt1': 23, 'alt2': None, 'volume': 24, 'marker': None},
        'STEERING':            {'main': 25, 'alt1': 26, 'alt2': None, 'volume': 27, 'marker': None},
        'SUSPENSION':          {'main': 28, 'alt1': 29, 'alt2': None, 'volume': 30, 'marker': None},
    }

    KNOWN_BRANDS = {
        'AUDI', 'BMW', 'MERCEDES-BENZ', 'HONDA', 'HONDA (RUS)', 'HONDA (USA)',
        'TOYOTA', 'NISSAN', 'NISSAN (USA)', 'MITSUBISHI', 'MAZDA', 'SUBARU',
        'LEXUS', 'LEXUS (USA)', 'INFINITI', 'HYUNDAI', 'HYUNDAI (RUS)', 'HYUNDAI (USA)',
        'KIA', 'LAND ROVER', 'JAGUAR', 'JEEP', 'CHRYSLER', 'DODGE',
        'DAIHATSU', 'DAIHATSU (RUS)', 'RENAULT', 'RENAULT (RUS)',
        'CITROËN', 'PEUGEOT', 'FORD', 'FORD (RUS)', 'FORD (USA)',
        'VOLVO', 'VW', 'VOLKSWAGEN', 'OPEL', 'SKODA', 'SEAT',
        'LADA (SHIGULI/VAZ)', 'LIFAN', 'GEELY', 'CHERY', 'TAGAZ',
        'MINI', 'FIAT', 'ALFA ROMEO', 'PORSCHE', 'SAAB',
    }

    # ─── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _clean(v) -> Optional[str]:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip()
        if not s or s.lower() in ('nan', 'none', '-'):
            return None
        return s

    @staticmethod
    def _normalize_brand(brand: str) -> str:
        if not brand:
            return ""
        brand = re.sub(r'\s*\([A-Z]+\)\s*', '', brand)
        brand = brand.replace('MERCEDES-BENZ', 'Mercedes-Benz')
        brand = brand.replace('CITROËN', 'Citroën')
        brand = brand.replace('SHIGULI/VAZ', 'Lada')
        result = brand.strip().title()
        result = result.replace('Vw', 'VW').replace('Bmw', 'BMW')
        return result

    @staticmethod
    def _extract_market(brand_raw: str) -> str:
        if not brand_raw:
            return 'EU'
        if '(RUS)' in brand_raw:
            return 'RU'
        if '(USA)' in brand_raw:
            return 'US'
        return 'EU'

    @staticmethod
    def _parse_year_range(year_str: str) -> tuple[Optional[int], Optional[int]]:
        """Парсит PVL-годы: '10- → 2010+, '00-'05 → 2000-2005, '95-'99 → 1995-1999.
        Правило: 2-значный год > 30 → 19xx, иначе 20xx.
        """
        if not year_str:
            return None, None
        s = str(year_str).strip()

        def expand_year(y2: int) -> int:
            return 2000 + y2 if y2 <= 30 else 1900 + y2

        m = re.match(r"^'(\d{2})\s*[-–]\s*$", s)
        if m:
            return expand_year(int(m.group(1))), None

        m = re.match(r"^'(\d{2})\s*[-–]\s*'?(\d{2})\s*$", s)
        if m:
            y1, y2 = m.groups()
            return expand_year(int(y1)), expand_year(int(y2))

        return None, None

    @staticmethod
    def _parse_engine_volume_from_model(model_name: str) -> Optional[float]:
        """Извлекает объём двигателя: 'A1 1.2 TFSI' → 1.2.
        Возвращает float для numeric(3,1) колонки engine_volume.
        """
        if not model_name:
            return None
        m = re.search(r'\b(\d+[.,]\d+)\s*(?:TFSI|TSI|FSI|TDI|d|i|V|T|CDI|CGI|GDI)?', model_name)
        if m:
            try:
                vol = float(m.group(1).replace(',', '.'))
                # numeric(3,1) вмещает 0.0–99.9 — обрежем
                if 0 < vol < 100:
                    return round(vol, 1)
            except ValueError:
                return None
        return None

    @staticmethod
    def _normalize_volume(v: Optional[str]) -> Optional[str]:
        """Сохраняет исходную строку PVL для applicability_conditions.volume_raw.
        Не парсит число — для этого есть _parse_volume_numeric.
        """
        if not v:
            return None
        s = str(v).strip()
        if not s or s in ('-', '·', ''):
            return None
        return s

    @staticmethod
    def _parse_volume_numeric(v: Optional[str]) -> Optional[float]:
        """Парсит PVL-объём в NUMERIC(5,2).
        Берёт ПЕРВОЕ число из строки:
          "2,1"       → 2.10
          "1,9-2,4"   → 1.90
          "0.5/0.7"   → 0.50
          "<"         → None
          "-"         → None
        """
        if not v:
            return None
        s = str(v).strip().replace(',', '.')
        # Ищем первое число (int или float)
        m = re.search(r'(\d+(?:\.\d+)?)', s)
        if not m:
            return None
        try:
            val = float(m.group(1))
            # numeric(5,2) вмещает 0.00–999.99 — обрежем
            if 0 < val < 1000:
                return round(val, 2)
        except ValueError:
            return None
        return None

    @staticmethod
    def _parse_viscosity(name: str) -> Optional[str]:
        if not name:
            return None
        m = re.search(r'(\d+W-?\d+)', name)
        return m.group(1) if m else None

    @staticmethod
    def _extract_brand_from_name(name: str) -> Optional[str]:
        if not name:
            return None
        for brand in ['G-Energy', 'Gazpromneft', 'G-Box', 'G-Truck', 'G-Force']:
            if name.startswith(brand):
                return brand
        return None

    @staticmethod
    def _split_model_name(full_name: str) -> tuple[str, Optional[str]]:
        """'A1 1.2 TFSI' → ('A1', '1.2 TFSI')."""
        if not full_name:
            return "", None
        m = re.search(r'\d', full_name)
        if m:
            idx = m.start()
            model = full_name[:idx].strip()
            sub_model = full_name[idx:].strip()
            return model if model else full_name, sub_model or None
        return full_name, None

    @staticmethod
    def _extract_product_line(name: str, brand: Optional[str]) -> Optional[str]:
        """'G-Energy F Synth 5W-40' → 'F Synth' (часть между брендом и вязкостью).
        ВНИМАНИЕ: import re должен быть в начале модуля (не использовать __import__('re')).
        """
        if not name or not brand:
            return None
        rest = name[len(brand):].strip()
        # Убираем вязкость (например "5W-40")
        rest = re.sub(r'\d+W-?\d+', '', rest).strip()
        # Убираем trailing punctuation
        rest = re.sub(r'[\s,]+$', '', rest).strip()
        return rest or None

    # ─── Detection (оптимизирован — не читает файл дважды) ─────

    def detect(self, file_path: str) -> bool:
        """Быстрая проверка первых 5 строк. Не парсит весь файл.
        Для оптимизации: результат можно передать в parse(file_path, df_head=df).
        """
        try:
            df_head = pd.read_excel(file_path, sheet_name=0, header=None, nrows=5)
            return self._detect_from_df(df_head)
        except Exception:
            return False

    def _detect_from_df(self, df_head: pd.DataFrame) -> bool:
        """Внутренний метод определения PVL-формата по уже загруженному DataFrame."""
        if len(df_head) < 2:
            return False
        row1 = df_head.iloc[1].astype(str).str.strip().tolist()
        return any('Легковые автомобили' in v for v in row1 if v != 'nan')

    # ─── Main parse ────────────────────────────────────────────

    def parse(self, file_path: str, df: Optional[pd.DataFrame] = None) -> list[PVLVehicleRecord]:
        """Парсит PVL-файл.

        Оптимизация: если df уже загружен (например, для detect()) — передай его,
        чтобы не читать файл повторно. Иначе будет read_excel внутри.
        """
        records: list[PVLVehicleRecord] = []
        if df is None:
            df = pd.read_excel(file_path, sheet_name=0, header=None)

        current_brand: Optional[str] = None
        current_generation: Optional[str] = None
        in_diesel_section = False
        current_market = 'EU'

        for i in range(3, len(df)):
            row = df.iloc[i]
            col0 = self._clean(row.iloc[0])

            if not col0:
                continue

            if col0 == 'Diesel':
                in_diesel_section = True
                continue

            if col0.upper().strip() in self.KNOWN_BRANDS:
                in_diesel_section = False
                current_brand = self._normalize_brand(col0)
                current_market = self._extract_market(col0)
                current_generation = None
                continue

            if re.match(r'^[A-Z]\d+\s*-\s*\w+', col0) and len(col0) < 60:
                current_generation = col0
                continue

            if re.match(r'^[A-Z]+-Class\s*\([A-Z]\d+\)', col0):
                current_generation = col0
                continue

            if re.match(r'^[a-z]{1,2}\s{2,}', col0):
                if records:
                    self._apply_footnote(records[-1], col0)
                continue

            if not current_brand:
                continue

            model_full = col0
            year_str = self._clean(row.iloc[1]) or ''
            year_start, year_end = self._parse_year_range(year_str)
            engine_oil_volume_raw = self._clean(row.iloc[2])
            engine_volume = self._parse_engine_volume_from_model(model_full)

            model, sub_model = self._split_model_name(model_full)
            if in_diesel_section:
                sub_model = f"Diesel {sub_model}" if sub_model else "Diesel"

            rec = PVLVehicleRecord(
                brand=current_brand,
                model=model,
                model_full=model_full,
                generation=current_generation,
                sub_model=sub_model,
                year_start=year_start,
                year_end=year_end,
                market=current_market,
                engine_volume=engine_volume,
                fuel_type='diesel' if in_diesel_section else 'petrol',
                engine_oil_volume_raw=engine_oil_volume_raw,
                row_number=i,
            )

            for pvl_node, cols in self.NODE_COLUMNS.items():
                main_fluid = self._clean(row.iloc[cols['main']]) if cols['main'] is not None and cols['main'] < len(row) else None
                alt1_fluid = self._clean(row.iloc[cols['alt1']]) if cols['alt1'] is not None and cols['alt1'] < len(row) else None
                alt2_fluid = self._clean(row.iloc[cols['alt2']]) if cols['alt2'] is not None and cols['alt2'] < len(row) else None
                volume_raw = self._clean(row.iloc[cols['volume']]) if cols['volume'] is not None and cols['volume'] < len(row) else None
                # volume_liters — NUMERIC(5,2): парсим первое число из PVL-строки
                volume_liters = self._parse_volume_numeric(volume_raw)
                # volume_raw сохраняем в conditions для отображения исходного диапазона
                volume_raw_normalized = self._normalize_volume(volume_raw)
                marker = self._clean(row.iloc[cols['marker']]) if cols['marker'] is not None and cols['marker'] < len(row) else None

                if main_fluid or alt1_fluid or alt2_fluid:
                    conditions = {}
                    if marker and marker not in (' ', '·'):
                        conditions['marker_code'] = marker
                    if in_diesel_section:
                        conditions['fuel_type'] = 'diesel'
                    # Сохраняем исходную строку объёма (например "1,9-2,4") для UI
                    if volume_raw_normalized:
                        conditions['volume_raw'] = volume_raw_normalized

                    # Маппим PVL-узел на существующие node_type + fluid_type
                    node_type, fluid_type = PVL_NODE_MAP[pvl_node]

                    if main_fluid and main_fluid not in ('-', '<', '< '):
                        rec.recommendations.append(PVLFluidRecommendation(
                            node_type=node_type,
                            fluid_type=fluid_type,
                            fluid_name=main_fluid,
                            fluid_brand=self._extract_brand_from_name(main_fluid),
                            viscosity_sae=self._parse_viscosity(main_fluid),
                            recommendation_rank=1,
                            is_oem=True,
                            volume_liters=volume_liters,
                            applicability_conditions=conditions.copy(),
                        ))
                    if alt1_fluid and alt1_fluid not in ('-',) and alt1_fluid != main_fluid:
                        rec.recommendations.append(PVLFluidRecommendation(
                            node_type=node_type,
                            fluid_type=fluid_type,
                            fluid_name=alt1_fluid,
                            fluid_brand=self._extract_brand_from_name(alt1_fluid),
                            viscosity_sae=self._parse_viscosity(alt1_fluid),
                            recommendation_rank=2,
                            is_oem=False,
                            volume_liters=volume_liters,
                            applicability_conditions=conditions.copy(),
                        ))
                    if alt2_fluid and alt2_fluid not in ('-',) and alt2_fluid != main_fluid and alt2_fluid != alt1_fluid:
                        rec.recommendations.append(PVLFluidRecommendation(
                            node_type=node_type,
                            fluid_type=fluid_type,
                            fluid_name=alt2_fluid,
                            fluid_brand=self._extract_brand_from_name(alt2_fluid),
                            viscosity_sae=self._parse_viscosity(alt2_fluid),
                            recommendation_rank=3,
                            is_oem=False,
                            volume_liters=volume_liters,
                            applicability_conditions=conditions.copy(),
                        ))

            if rec.recommendations:
                records.append(rec)

        logger.info(f"PVLParser: parsed {len(records)} vehicles, "
                    f"{sum(len(r.recommendations) for r in records)} recommendations")
        return records

    def _apply_footnote(self, record: PVLVehicleRecord, footnote: str) -> None:
        """Применяет сноску к последней записи как доп. рекомендацию (rank 4+)."""
        m = re.match(r'^([a-z]{1,2})\s{2,}(.+)$', footnote)
        if not m:
            return
        marker, body = m.groups()

        # Определяем node_type по ключевым словам
        node_code = None
        for pattern, code in FOOTNOTE_NODE_MAP:
            if re.search(pattern, body.lower()):
                node_code = code
                break
        if not node_code:
            return

        fluid_type = NODE_TO_FLUID_TYPE.get(node_code, 'engine_oil')

        vol_match = re.search(r'([\d,\-\s]+)\s*л', body)
        volume_raw = vol_match.group(1).strip() if vol_match else None
        volume_liters = self._parse_volume_numeric(volume_raw)

        oil_part = body.split(':', 1)[-1] if ':' in body else body
        oils = [o.strip() for o in oil_part.split(';') if o.strip() and o.strip() != '-']
        if not oils:
            return

        existing_ranks = [r.recommendation_rank for r in record.recommendations
                          if r.node_type == node_code]
        next_rank = max(existing_ranks) + 1 if existing_ranks else 4

        # Особый случай: "передний и задний дифференциалы" — добавим пометку
        conditions = {'footnote_marker': marker, 'source': 'pvl_footnote'}
        if 'передний и задний' in body.lower():
            conditions['also_rear'] = True
        if volume_raw:
            conditions['volume_raw'] = volume_raw

        for oil_name in oils:
            record.recommendations.append(PVLFluidRecommendation(
                node_type=node_code,
                fluid_type=fluid_type,
                fluid_name=oil_name,
                fluid_brand=self._extract_brand_from_name(oil_name),
                viscosity_sae=self._parse_viscosity(oil_name),
                recommendation_rank=next_rank,
                is_oem=False,
                volume_liters=volume_liters,
                applicability_conditions=conditions.copy(),
            ))
            next_rank += 1
```

═══════════════════════════════════════════════════════════════════════════════
7. ИНТЕГРАЦИЯ В ETL-КОНВЕЙЕР
═══════════════════════════════════════════════════════════════════════════════

7.1. В backend/app/services/etl_pipeline.py добавь функцию:

```python
import json
import hashlib
from typing import Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pvl_parser import PVLParser, PVLVehicleRecord, PVLFluidRecommendation


async def process_pvl_batch(
    file_path: str,
    batch_id: str,
    company_id: str,                # ← company_id, НЕ tenant_id
    db: AsyncSession,
) -> dict:
    """Импорт PVL-каталога в существующие таблицы."""
    parser = PVLParser()
    if not parser.detect(file_path):
        raise ValueError("File is not a PVL catalog")

    records = parser.parse(file_path)
    logger.info(f"PVL: parsed {len(records)} vehicles, "
                f"{sum(len(r.recommendations) for r in records)} recommendations")

    stats = {
        'parser': 'PVLParser',
        'parsed': len(records),
        'inserted_brands': 0,
        'inserted_models': 0,
        'inserted_variants': 0,
        'inserted_fluids': 0,
        'inserted_recommendations': 0,
        'skipped_duplicates': 0,
        'errors': [],
    }

    # Кэши для дедупликации в пределах файла
    brand_cache: dict[str, str] = {}    # name_ru → id
    model_cache: dict[str, str] = {}    # "brand_id|name|generation" → id
    variant_cache: set[str] = set()     # source_hash
    fluid_cache: dict[str, str] = {}    # canonical_name → id

    for record in records:
        try:
            # 1. Brand
            brand_key = record.brand.lower()
            if brand_key not in brand_cache:
                brand_id = await _upsert_brand(db, company_id, record.brand, record.market)
                if brand_id:
                    brand_cache[brand_key] = brand_id
                    stats['inserted_brands'] += 1
                else:
                    continue
            brand_id = brand_cache[brand_key]

            # 2. Model
            model_key = f"{brand_id}|{record.model}|{record.generation or ''}"
            if model_key not in model_cache:
                model_id = await _upsert_model(db, company_id, brand_id, record.model, record.generation)
                if model_id:
                    model_cache[model_key] = model_id
                    stats['inserted_models'] += 1
                else:
                    continue
            model_id = model_cache[model_key]

            # 3. Variant
            source_hash = record.source_hash()
            if source_hash in variant_cache:
                stats['skipped_duplicates'] += 1
                continue
            variant_id = await _upsert_variant(db, company_id, model_id, record, source_hash)
            if not variant_id:
                continue
            variant_cache.add(source_hash)
            stats['inserted_variants'] += 1

            # 4. Recommendations
            for rec in record.recommendations:
                fluid_id = fluid_cache.get(rec.fluid_name)
                if not fluid_id:
                    fluid_id = await _upsert_fluid(
                        db, company_id, rec.fluid_name,
                        rec.fluid_brand, rec.viscosity_sae, rec.fluid_type
                    )
                    if fluid_id:
                        fluid_cache[rec.fluid_name] = fluid_id
                        stats['inserted_fluids'] += 1

                await _upsert_recommendation(
                    db, company_id, variant_id, rec, fluid_id
                )
                stats['inserted_recommendations'] += 1

        except Exception as e:
            logger.exception(f"Error processing PVL row {record.row_number}: {e}")
            stats['errors'].append({
                'row': record.row_number,
                'vehicle': f"{record.brand} {record.model_full}",
                'error': str(e),
            })

        if (len(variant_cache) % 500) == 0 and len(variant_cache) > 0:
            await db.commit()
            logger.info(f"  PVL progress: {len(variant_cache)} variants")

    await db.commit()

    # 5. Qdrant индексация (через Celery)
    from app.tasks.etl_tasks import index_qdrant_for_batch
    index_qdrant_for_batch.delay(batch_id, company_id)

    return stats


async def _upsert_brand(db: AsyncSession, company_id: str, name_ru: str, market: str) -> Optional[str]:
    """Создаёт или находит бренд. Возвращает id.
    ВНИМАНИЕ: используется name_ru (НЕ name), company_id (НЕ tenant_id).
    """
    result = await db.execute(
        text("""
            INSERT INTO car_brands (company_id, name_ru, vehicle_type, market)
            VALUES (:cid, :name_ru, 'passenger_car', :market)
            ON CONFLICT (company_id, name_ru) DO UPDATE
                SET market = COALESCE(car_brands.market, EXCLUDED.market),
                    vehicle_type = COALESCE(car_brands.vehicle_type, EXCLUDED.vehicle_type)
            RETURNING id
        """),
        {"cid": company_id, "name_ru": name_ru, "market": market}
    )
    row = result.fetchone()
    return str(row[0]) if row else None


async def _upsert_model(db: AsyncSession, company_id: str, brand_id: str,
                        name: str, generation: Optional[str]) -> Optional[str]:
    """Создаёт или находит модель. Возвращает id.
    UNIQUE constraint: (brand_id, name, generation, company_id)
    """
    result = await db.execute(
        text("""
            INSERT INTO car_models (company_id, brand_id, name, generation)
            VALUES (:cid, :bid, :name, :gen)
            ON CONFLICT (brand_id, name, generation, company_id) DO NOTHING
            RETURNING id
        """),
        {"cid": company_id, "bid": brand_id, "name": name, "gen": generation}
    )
    row = result.fetchone()
    if row:
        return str(row[0])
    # Уже существует — найдём
    result = await db.execute(
        text("""
            SELECT id FROM car_models
            WHERE brand_id = :bid AND name = :name
              AND COALESCE(generation, '') = COALESCE(:gen, '')
              AND company_id = :cid
        """),
        {"bid": brand_id, "name": name, "gen": generation, "cid": company_id}
    )
    row = result.fetchone()
    return str(row[0]) if row else None


async def _upsert_variant(db: AsyncSession, company_id: str, model_id: str,
                          record: PVLVehicleRecord, source_hash: str) -> Optional[str]:
    """Создаёт variant. Возвращает id.
    ВНИМАНИЕ: используется engine_volume (НЕ displacement_liters),
              body_type = NULL (НЕ body_number).
    """
    attributes = {
        'engine_oil_volume_raw': record.engine_oil_volume_raw,
        'pvl_source': True,
        'pvl_row': record.row_number,
    }
    result = await db.execute(
        text("""
            INSERT INTO car_variants
                (company_id, model_id, body_type, year_start, year_end,
                 engine_code, engine_volume, fuel_type, drive_type,
                 transmission_type, sub_model, market, attributes, source_hash)
            VALUES
                (:cid, :mid, NULL, :ys, :ye, NULL, :evolume, :ft, NULL, NULL,
                 :sub, :market, CAST(:attrs AS jsonb), :hash)
            ON CONFLICT (company_id, source_hash) DO NOTHING
            RETURNING id
        """),
        {
            "cid": company_id, "mid": model_id,
            "ys": record.year_start, "ye": record.year_end,
            "evolume": record.engine_volume,
            "ft": record.fuel_type,
            "sub": record.sub_model,
            "market": record.market,
            "attrs": json.dumps(attributes),
            "hash": source_hash,
        }
    )
    row = result.fetchone()
    return str(row[0]) if row else None


async def _upsert_fluid(db: AsyncSession, company_id: str, canonical_name: str,
                        brand: Optional[str], viscosity_sae: Optional[str],
                        fluid_type: str) -> Optional[str]:
    """Создаёт fluid. Возвращает id.
    fluid_type — СТРОГО из существующего enum: engine_oil, manual_transmission,
    auto_transmission, cvt, differential, transfer_case, steering, brake,
    coolant, suspension.
    """
    hash_sig = hashlib.sha256(canonical_name.encode()).hexdigest()[:16]

    # ВАЖНО: CAST(:ftype AS fluid_type) вместо :ftype::fluid_type
    # asyncpg не переваривает named param + :: cast (см. фикс в sales_copilot.py)
    result = await db.execute(
        text("""
            INSERT INTO fluids
                (company_id, canonical_name, brand, product_line,
                 viscosity_sae, fluid_type, hash_signature)
            VALUES
                (:cid, :name, :brand, :pline, :visc,
                 CAST(:ftype AS fluid_type), :hash)
            ON CONFLICT (company_id, hash_signature) DO NOTHING
            RETURNING id
        """),
        {
            "cid": company_id, "name": canonical_name, "brand": brand,
            "pline": _extract_product_line(canonical_name, brand),
            "visc": viscosity_sae, "ftype": fluid_type, "hash": hash_sig,
        }
    )
    row = result.fetchone()
    if row:
        return str(row[0])
    result = await db.execute(
        text("SELECT id FROM fluids WHERE company_id = :cid AND hash_signature = :hash"),
        {"cid": company_id, "hash": hash_sig}
    )
    row = result.fetchone()
    return str(row[0]) if row else None


def _extract_product_line(name: str, brand: Optional[str]) -> Optional[str]:
    """'G-Energy F Synth 5W-40' → 'F Synth'.
    ВАЖНО: модуль re импортирован в начале файла (не использовать __import__('re')).
    """
    if not name or not brand:
        return None
    rest = name[len(brand):].strip()
    rest = re.sub(r'\d+W-?\d+', '', rest).strip()
    rest = re.sub(r'[\s,]+$', '', rest).strip()
    return rest or None


async def _upsert_recommendation(db: AsyncSession, company_id: str,
                                  variant_id: str, rec: PVLFluidRecommendation,
                                  fluid_id: Optional[str]):
    """Создаёт recommendation.
    UNIQUE constraint: (company_id, car_variant_id, node_type, recommendation_rank)
    Если fluid_id None — сохраняем fluid_name_override.

    ВАЖНО: volume_liters — NUMERIC(5,2), передаём float (не строку).
    ВАЖНО: CAST(:node AS node_type) вместо :node::node_type (asyncpg fix).
    """
    await db.execute(
        text("""
            INSERT INTO recommendations
                (company_id, car_variant_id, node_type, fluid_id,
                 fluid_name_override, recommendation_rank,
                 is_oem_recommendation, volume_liters,
                 applicability_conditions, source)
            VALUES
                (:cid, :vid, CAST(:node AS node_type), :fid,
                 :foverride, :rank,
                 :oem, :vol,
                 CAST(:cond AS jsonb), 'pvl')
            ON CONFLICT (company_id, car_variant_id, node_type, recommendation_rank)
                DO UPDATE SET
                    fluid_id = EXCLUDED.fluid_id,
                    fluid_name_override = EXCLUDED.fluid_name_override,
                    is_oem_recommendation = EXCLUDED.is_oem_recommendation,
                    volume_liters = EXCLUDED.volume_liters,
                    applicability_conditions = EXCLUDED.applicability_conditions
        """),
        {
            "cid": company_id, "vid": variant_id,
            "node": rec.node_type,
            "fid": fluid_id,
            "foverride": rec.fluid_name if not fluid_id else None,
            "rank": rec.recommendation_rank,
            "oem": rec.is_oem,
            "vol": rec.volume_liters,  # float или None (NUMERIC(5,2))
            "cond": json.dumps(rec.applicability_conditions),
        }
    )
```

7.2. В backend/app/services/etl_pipeline.py обнови точку входа:

```python
from app.services.pvl_parser import PVLParser

async def process_import_batch(file_path: str, batch_id: str, company_id: str, db: AsyncSession):
    """Main ETL entry point — auto-detects format."""
    # Сначала проверяем PVL
    pvl_parser = PVLParser()
    if pvl_parser.detect(file_path):
        return await process_pvl_batch(file_path, batch_id, company_id, db)

    # Иначе — японский каталог (существующая логика без изменений)
    return await _process_japanese_batch(file_path, batch_id, company_id, db)
```

═══════════════════════════════════════════════════════════════════════════════
8. ОБНОВЛЕНИЕ QDRANT ИНДЕКСАЦИИ
═══════════════════════════════════════════════════════════════════════════════

В существующем vector_indexer.py обнови payload точки Qdrant:

```python
payload = {
    "company_id": str(company_id),        # ← company_id, НЕ tenant_id
    "car_variant_id": str(rec.car_variant_id),
    "node_type": rec.node_type,
    "fluid_id": str(rec.fluid_id) if rec.fluid_id else None,
    "fluid_name": (rec.fluid.canonical_name if rec.fluid else rec.fluid_name_override),
    "fluid_brand": rec.fluid.brand if rec.fluid else None,
    "viscosity_sae": rec.fluid.viscosity_sae if rec.fluid else None,
    "fluid_type": rec.fluid.fluid_type if rec.fluid else None,
    # НОВЫЕ ПОЛЯ:
    "recommendation_rank": rec.recommendation_rank,
    "is_oem": rec.is_oem_recommendation,
    "applicability_conditions": rec.applicability_conditions or {},
    "volume_liters": rec.volume_liters,
}
```

Создай payload-индексы в Qdrant (один раз):
```python
await qdrant.create_payload_index("recommendations", "recommendation_rank", "integer")
await qdrant.create_payload_index("recommendations", "is_oem", "bool")
await qdrant.create_payload_index("recommendations", "company_id", "keyword")
```

═══════════════════════════════════════════════════════════════════════════════
9. ОБНОВЛЕНИЕ API ПОИСКА
═══════════════════════════════════════════════════════════════════════════════

В backend/app/routers/search.py:

```python
class RecommendationResponse(BaseModel):
    id: str
    node_type: str
    fluid_id: Optional[str]
    fluid_name: str
    fluid_brand: Optional[str]
    viscosity_sae: Optional[str]
    fluid_type: Optional[str]
    recommendation_rank: int = 1
    is_oem: bool = False
    volume_liters: Optional[float]    # NUMERIC(5,2) — парсенное число
    volume_raw: Optional[str] = None  # берётся из applicability_conditions.volume_raw
    applicability_conditions: dict = {}

class NodeGroupResult(BaseModel):
    node_type: str
    node_label: str
    recommendations: list[RecommendationResponse]  # отсортированы по rank

class SearchResponse(BaseModel):
    vehicle: VehicleInfo
    groups: list[NodeGroupResult]
```

SQL-запрос поиска (с реальными именами колонок):
```sql
SELECT
    r.id,
    r.node_type,
    r.fluid_id,
    r.recommendation_rank,
    r.is_oem_recommendation,
    r.volume_liters,
    r.applicability_conditions,
    COALESCE(f.canonical_name, r.fluid_name_override) AS fluid_name,
    f.brand AS fluid_brand,
    f.viscosity_sae,
    f.fluid_type
FROM recommendations r
LEFT JOIN fluids f ON f.id = r.fluid_id
WHERE r.car_variant_id = :vid
  AND r.company_id = :cid     -- RLS
ORDER BY r.node_type, r.recommendation_rank
```

═══════════════════════════════════════════════════════════════════════════════
10. ОБНОВЛЕНИЕ FRONTEND
═══════════════════════════════════════════════════════════════════════════════

10.1. FluidCard.tsx — поддержка рангов (без изменений из v3.0):

```tsx
const RANK_CONFIG = {
  1: { label: '★ Основное', color: 'var(--success)', badgeClass: 'badge-oem' },
  2: { label: 'Alt 1',      color: 'var(--info)',    badgeClass: 'badge-approval' },
  3: { label: 'Alt 2',      color: 'var(--sidebar-muted)', badgeClass: 'badge-alternative' },
  4: { label: 'Доп. (сноска)', color: 'var(--accent)', badgeClass: 'badge-warning' },
  5: { label: 'Доп. (сноска)', color: 'var(--accent)', badgeClass: 'badge-warning' },
};
// ... рендер как в v3.0
```

10.2. В search/page.tsx — группировка по node_type + сортировка по rank (без изменений из v3.0).

═══════════════════════════════════════════════════════════════════════════════
11. ПОРЯДОК ВЫПОЛНЕНИЯ (7 ШАГОВ С КОММИТАМИ)
═══════════════════════════════════════════════════════════════════════════════

ШАГ 1: СВЕРКА С РЕАЛЬНОЙ СХЕМОЙ (КРИТИЧНО!)
  - Выполни команды из шага 2 (Inventory)
  - Убедись, что имена колонок и enum совпадают с тем, что в промпте
  - Если есть расхождения — СООБЩИ о них перед продолжением
  - COMMIT: "chore(pvl): шаг 1 — inventory реальной схемы БД"

ШАГ 2: Применить миграцию (см. шаг 5)
  - COMMIT: "feat(pvl): шаг 2 — миграция БД (vehicle_type, market, sub_model, recommendation_rank, SUSPENSION)"

ШАГ 3: Создать pvl_parser.py (см. шаг 6)
  - Протестируй standalone:
    python -c "from app.services.pvl_parser import PVLParser; p = PVLParser(); r = p.parse('/path/to/PVL.xlsx'); print(f'{len(r)} vehicles, {sum(len(x.recommendations) for x in r)} recs')"
  - Ожидаемый результат: 2929 vehicles, ~21762 recommendations
  - COMMIT: "feat(pvl): шаг 3 — PVL-парсер с реальными именами колонок"

ШАГ 4: Расширить ETL-конвейер (см. шаг 7)
  - COMMIT: "feat(pvl): шаг 4 — интеграция в ETL с автоопределением формата"

ШАГ 5: Обновить Qdrant (см. шаг 8)
  - COMMIT: "feat(pvl): шаг 5 — Qdrant payload расширен (rank, conditions, company_id)"

ШАГ 6: Импортировать PVL-каталог
  - Загрузи через /api/v1/imports/upload или напрямую через Celery
  - Проверь:
    psql -c "SELECT COUNT(*) FROM car_brands WHERE market IN ('EU','US','RU');"
    psql -c "SELECT market, COUNT(*) FROM car_brands GROUP BY market;"
    psql -c "SELECT COUNT(*) FROM car_variants WHERE market IN ('EU','US','RU');"
    psql -c "SELECT recommendation_rank, COUNT(*) FROM recommendations WHERE source='pvl' GROUP BY recommendation_rank ORDER BY 1;"
  - Ожидаемый результат:
    car_brands: +36 (стало ~44)
    car_variants: +2929 (стало ~5165)
    recommendations: +21762 (стало ~32929)
  - COMMIT: "feat(pvl): шаг 6 — импорт PVL-каталога (2929 авто, 21762 рекомендаций)"

ШАГ 7: Обновить Frontend
  - COMMIT: "feat(pvl): шаг 7 — UI показывает 3 ранга масел (primary/alt1/alt2)"

═══════════════════════════════════════════════════════════════════════════════
12. ТРЕБОВАНИЯ К КОДУ (КРИТИЧНО)
═══════════════════════════════════════════════════════════════════════════════

1. ❌ НИКАКИХ # TODO, pass, raise NotImplementedError
2. ✅ Строгая типизация (Pydantic V2, TypeScript strict)
3. ✅ Русский язык в комментариях и UI
4. ✅ Multi-tenancy через RLS — ВСЕ запросы фильтруются по company_id
5. ✅ Backward compatibility:
   - Существующие эндпоинты /api/v1/* продолжают работать
   - Старые рекомендации (rank=NULL) показываются как rank=1
   - Старые car_brands получают vehicle_type='passenger_car', market='JDM'
6. ✅ Производительность:
   - Парсинг 2929 авто — < 5 секунд
   - Импорт в БД — < 60 секунд (батчами по 500 с commit)
   - Qdrant индексация — < 30 секунд
7. ✅ ИСПОЛЬЗУЙ ТОЛЬКО РЕАЛЬНЫЕ ИМЕНА КОЛОНОК (из шага 2)

═══════════════════════════════════════════════════════════════════════════════
13. ТИПИЧНЫЕ ОШИБКИ (ИЗБЕГАЙ!)
═══════════════════════════════════════════════════════════════════════════════

❌ ОШИБКА 1: Использовать tenant_id вместо company_id
✅ ПРАВИЛЬНО: company_id везде (SQL, Python, RLS policies, Qdrant payload).

❌ ОШИБКА 2: Использовать name вместо name_ru в car_brands
✅ ПРАВИЛЬНО: car_brands.name_ru — это РЕАЛЬНОЕ имя колонки.

❌ ОШИБКА 3: Использовать displacement_liters / body_number
✅ ПРАВИЛЬНО: car_variants.engine_volume (numeric(3,1)) / car_variants.body_type.

❌ ОШИБКА 4: Маппить PVL-систему на несуществующий fluid_type
✅ ПРАВИЛЬНО: Используй PVL_NODE_MAP (см. шаг 6):
   ENGINE → (ENGINE, engine_oil)
   MANUAL_TRANSMISSION → (MANUAL_TRANSMISSION, manual_transmission)
   AUTO_TRANSMISSION → (AUTO_TRANSMISSION, auto_transmission)
   DIFFERENTIAL → (FRONT_DIFF, differential)
   COOLANT → (COOLANT, coolant)
   BRAKE → (BRAKE, brake)
   STEERING → (STEERING, steering)
   SUSPENSION → (SUSPENSION, suspension)

❌ ОШИБКА 5: Использовать DIFFERENTIAL как node_type
✅ ПРАВИЛЬНО: node_type enum не содержит DIFFERENTIAL.
   Используй FRONT_DIFF (дефолт) или REAR_DIFF (из сносок "задний дифференциал").

❌ ОШИБКА 6: Использовать старый UNIQUE constraint
✅ ПРАВИЛЬНО: UNIQUE (company_id, car_variant_id, node_type, recommendation_rank).
   Обязательно с company_id (RLS!).

❌ ОШИБКА 7: Пропускать Diesel-секции
✅ ПРАВИЛЬНО: in_diesel_section=True → fuel_type='diesel', sub_model='Diesel ...'.
   Это 1305 записей (44.6% каталога).

❌ ОШИБКА 8: Игнорировать сноски
✅ ПРАВИЛЬНО: Парсить как rank 4+ с applicability_conditions.
   Это 455 детальных спецификаций.

❌ ОШИБКА 9: Положить "1.2 TFSI" в engine_code
✅ ПРАВИЛЬНО: model="A1", sub_model="1.2 TFSI", engine_code=NULL.

❌ ОШИБКА 10: Считать col 2 = объём двигателя
✅ ПРАВИЛЬНО: col 2 = ОБЪЁМ МАСЛА двигателя. Объём двигателя извлекай из названия.

❌ ОШИБКА 11: Парсить '95-'99 как 2095-2099
✅ ПРАВИЛЬНО: 2-значный год > 30 → 19xx, иначе 20xx.

❌ ОШИБКА 12: car_models UNIQUE в неправильном порядке
✅ ПРАВИЛЬНО: (brand_id, name, generation, company_id) — порядок важен в ON CONFLICT.

❌ ОШИБКА 13: Забывать applicability_conditions
✅ ПРАВИЛЬНО: Сохраняй маркеры (u, a, c, d, ...), conditions (Diesel, also_rear, ...),
   и volume_raw (исходную строку PVL).

❌ ОШИБКА 14: Удалять существующие данные
✅ ПРАВИЛЬНО: ON CONFLICT DO NOTHING / DO UPDATE. Существующие 11 167 рекомендаций JDM не трогать.

❌ ОШИБКА 15: Не запускать Qdrant индексацию
✅ ПРАВИЛЬНО: После импорта вызывай index_qdrant_for_batch.delay(batch_id, company_id).

❌ ОШИБКА 16: Использовать :node::node_type (PostgreSQL cast)
✅ ПРАВИЛЬНО: CAST(:node AS node_type). asyncpg НЕ переваривает named param + :: cast.
   Это_known_issue в проекте — тот же фикс применён в sales_copilot.py:77.
   Относится ко ВСЕМ enum-колонкам: node_type, fluid_type, и к jsonb/JSONB casts.

❌ ОШИБКА 17: Передавать volume_liters как строку
✅ ПРАВИЛЬНО: volume_liters — NUMERIC(5,2) в БД.
   Передавай float (2.1, 1.9, 0.5) или None.
   Для PVL-строк типа "1,9-2,4" или "<" парси первое число через _parse_volume_numeric().
   Исходную строку сохраняй в applicability_conditions.volume_raw.

❌ ОШИБКА 18: Использовать __import__('re') в коде
✅ ПРАВИЛЬНО: import re в начале модуля. Это Python-стиль, не хак.

❌ ОШИБКА 19: Динамический поиск constraint по ordinal positions
✅ ПРАВИЛЬНО: DROP INDEX IF EXISTS с прямым именем (например uq_recommendations_variant_node_fluid).
   Перед миграцией проверь реальное имя через: \di recommendations

❌ ОШИБКА 20: Читать Excel дважды (detect + parse)
✅ ПРАВИЛЬНО: detect() читает только nrows=5. parse(file_path, df=...) принимает
   уже загруженный DataFrame, чтобы избежать повторного чтения 29MB файла.
   Для большой нагрузки — кэшируй DataFrame в Celery task.

❌ ОШИБКА 21: Использовать VARCHAR для volume_liters
✅ ПРАВИЛЬНО: volume_liters — NUMERIC(5,2). Если в PVL "2,1" — парси в 2.10.
   Если "<" или "-" — None. Исходную строку клади в conditions.volume_raw.

═══════════════════════════════════════════════════════════════════════════════
14. ЧТО ДЕЛАТЬ ПОСЛЕ ВЫПОЛНЕНИЯ
═══════════════════════════════════════════════════════════════════════════════

После шага 7 сообщи:
  1. Список созданных/изменённых файлов
  2. Результат миграции:
     psql -c "\d car_brands" | grep -E "(vehicle_type|market)"
     psql -c "\d car_variants" | grep -E "(sub_model|market|attributes)"
     psql -c "\d recommendations" | grep -E "(recommendation_rank|applicability|fluid_name_override)"
     psql -c "SELECT enum_range(NULL::node_type);"   | должно включать SUSPENSION
     psql -c "SELECT enum_range(NULL::fluid_type);"  | должно включать suspension
  3. Результат импорта:
     psql -c "SELECT market, COUNT(*) FROM car_brands GROUP BY market;"
     psql -c "SELECT market, COUNT(*) FROM car_variants GROUP BY market;"
     psql -c "SELECT recommendation_rank, COUNT(*) FROM recommendations GROUP BY recommendation_rank ORDER BY 1;"
  4. Результат Qdrant:
     curl http://localhost:6333/collections/recommendations
  5. Время каждого шага
  6. Любые отклонения

═══════════════════════════════════════════════════════════════════════════════
15. ЕСЛИ ЧТО-ТО НЕПОНЯТНО
═══════════════════════════════════════════════════════════════════════════════

- Открой /home/g/gsm/vehicle-architecture/import_pvl.py
  Это готовый standalone скрипт с проверенной логикой парсинга.
  Но ВНИМАНИЕ: там используются СТАРЫЕ имена (tenant_id, name, displacement_liters).
  Адаптируй логику, но НЕ копируй SQL/Python дословно.

- Открой /home/g/gsm/vehicle-architecture/PVL_IMPORT_GUIDE.md
  Детальный отчёт: что внутри файла, структура колонок, чек-лист.

- Открой /home/z/my-project/upload/Каталог подбора PVL.xlsx
  Сам файл для тестирования парсера.

Начинай с ШАГА 1 (inventory реальной схемы). После каждого шага — коммит и отчёт.
Удачи! 🚀
