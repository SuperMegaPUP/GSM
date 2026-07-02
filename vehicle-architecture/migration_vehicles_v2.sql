-- ============================================================================
-- GSM Vehicle Architecture 2.0 — Polymorphic Vehicle Model
-- ============================================================================
-- ЦЕЛЬ: Поддержка разных типов техники (легковые, грузовые, мото, бензопилы,
-- газонокосилки) в единой схеме без переписывания при добавлении новых типов.
--
-- ПРИНЦИПЫ:
--   1. Single Table Inheritance + JSONB для type-specific атрибутов
--      (вместо table-per-class — проще миграции, проще аналитика)
--   2. Полиморфные узлы (node_code) — разные наборы для каждого типа техники
--   3. Рекомендации с рангом (1=primary, 2=alt1, 3=alt2) — для PVL-формата
--   4. Backward compatible: старая таблица car_variants остаётся как view
-- ============================================================================

-- ============================================================================
-- 1. Vehicle types enum — расширяемый список типов техники
-- ============================================================================
DO $$ BEGIN
    CREATE TYPE vehicle_type AS ENUM (
        'passenger_car',     -- легковые авто (включая JDM, PVL, РФ, EU, USA)
        'light_commercial',  -- лёгкие коммерческие (LCV: фургоны, пикапы до 3.5т)
        'heavy_truck',       -- грузовые тяжёлые (более 3.5т)
        'heavy_equipment',   -- спецтехника (экскаваторы, бульдозеры, погрузчики)
        'agricultural',      -- сельхозтехника (тракторы, комбайны)
        'motorcycle',        -- мотоциклы, скутеры, квадроциклы
        'marine',            -- лодочные моторы, водная техника
        'small_engine',      -- малая техника (бензопилы, газонокосилки, генераторы)
        'industrial'         -- промышленное оборудование (компрессоры, редукторы)
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 2. Polymorphic vehicles — единая таблица для ВСЕХ типов техники
-- ============================================================================
CREATE TABLE IF NOT EXISTS vehicles (
    id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID           NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'::uuid,

    -- Тип техники (дискриминатор)
    vehicle_type    vehicle_type   NOT NULL,

    -- Универсальные идентификационные поля (есть у всех типов)
    brand           VARCHAR(100)   NOT NULL,           -- Toyota, Caterpillar, Stihl, Honda
    model           VARCHAR(200)   NOT NULL,           -- Hilux Surf, 320D, MS-180
    generation      VARCHAR(100),                      -- W164, VIII поколение
    sub_model       VARCHAR(200),                      -- Diesel, Quattro, 4Motion, Hybrid

    -- Год выпуска (универсально для всех)
    year_start      INTEGER,                           -- 1998
    year_end        INTEGER,                           -- NULL = по настоящее время

    -- Market (для легковых и грузовиков — JDM/EU/US/RU; для прочих — NULL)
    market          VARCHAR(20),

    -- Type-specific атрибуты в JSONB (разная структура для разных типов)
    -- См. примеры структур ниже в комментариях
    attributes      JSONB          NOT NULL DEFAULT '{}'::jsonb,

    -- Источник данных
    source          VARCHAR(50)    NOT NULL,           -- 'japan_catalog', 'pvl', 'manual', 'import'
    source_hash     VARCHAR(64),                       -- SHA-256 от нормализованных ключевых полей
    external_codes  JSONB          DEFAULT '{}'::jsonb,-- {body_number: "LA-CL7", engine_code: "K20A", vin_pattern: "..."}

    -- Метаданные
    is_published    BOOLEAN        NOT NULL DEFAULT true,
    needs_review    BOOLEAN        NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    created_by      UUID           REFERENCES users(id) ON DELETE SET NULL,

    -- Уникальность по типу + бренду + модели + поколению + хэшу источника
    CONSTRAINT vehicles_unique UNIQUE (vehicle_type, brand, model, generation, sub_model, source_hash)
);

-- Примеры структур attributes для разных vehicle_type:
--
-- passenger_car: {
--   "engine_code": "K20A",
--   "engine_family": "K-Series",
--   "displacement_liters": 2.0,
--   "fuel_type": "petrol",        -- petrol|diesel|hybrid|electric|lpg
--   "engine_power_kw": 147,
--   "drive_type": "2WD",          -- 2WD|4WD|AWD|FWD|RWD
--   "transmission_type": "MT",    -- MT|AT|CVT|AMT|DCT
--   "body_style": "sedan",        -- sedan|hatchback|suv|coupe|wagon|pickup|van
--   "body_number": "LA-CL7"
-- }
--
-- heavy_truck: {
--   "gvwr_kg": 24000,             -- gross vehicle weight rating
--   "engine_power_kw": 350,
--   "engine_displacement_liters": 11.9,
--   "fuel_type": "diesel",
--   "axle_config": "6x4",         -- 4x2|6x2|6x4|8x4|10x4
--   "transmission_type": "AMT",
--   "application": "long_haul"    -- long_haul|construction|municipal|refuse
-- }
--
-- heavy_equipment: {
--   "operating_weight_kg": 25000,
--   "engine_power_kw": 150,
--   "engine_displacement_liters": 7.0,
--   "equipment_type": "excavator",  -- excavator|bulldozer|loader|grader|crane
--   "hydraulic_system_capacity_liters": 200,
--   "application": "construction"
-- }
--
-- motorcycle: {
--   "engine_displacement_cc": 600,
--   "engine_type": "4-stroke",     -- 2-stroke|4-stroke|electric
--   "cooling": "liquid",           -- air|liquid|oil
--   "motorcycle_type": "sport",    -- sport|cruiser|touring|enduro|scooter|atv
--   "transmission_type": "MT"
-- }
--
-- small_engine (бензопилы/газонокосилки): {
--   "engine_displacement_cc": 50,
--   "engine_type": "2-stroke",
--   "fuel_mix_ratio": "1:50",      -- для 2-тактных
--   "equipment_type": "chainsaw",  -- chainsaw|lawn_mower|trimmer|generator|snowblower
--   "bar_length_cm": 40            -- для бензопил
-- }

-- ============================================================================
-- 3. Indexes для vehicles
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_vehicles_tenant_type
    ON vehicles (tenant_id, vehicle_type);

CREATE INDEX IF NOT EXISTS idx_vehicles_type_brand
    ON vehicles (vehicle_type, brand);

CREATE INDEX IF NOT EXISTS idx_vehicles_type_brand_model
    ON vehicles (vehicle_type, brand, model);

CREATE INDEX IF NOT EXISTS idx_vehicles_year
    ON vehicles (vehicle_type, year_start, year_end);

-- GIN для поиска по JSONB attributes
CREATE INDEX IF NOT EXISTS idx_vehicles_attributes_gin
    ON vehicles USING gin (attributes jsonb_path_ops);

-- FTS для текстового поиска
CREATE INDEX IF NOT EXISTS idx_vehicles_fts
    ON vehicles USING gin (
        to_tsvector('russian',
            brand || ' ' || model || ' ' || coalesce(generation, '') || ' ' || coalesce(sub_model, '')
        )
    );

CREATE INDEX IF NOT EXISTS idx_vehicles_published
    ON vehicles (vehicle_type, is_published, needs_review)
    WHERE is_published = true AND needs_review = false;

-- ============================================================================
-- 4. Row-Level Security
-- ============================================================================
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles FORCE ROW LEVEL SECURITY;

-- Seed-данные (is_seed) доступны всем тенантам
-- (позже добавим поле is_seed, пока считаем, что source_hash = 'seed_*' означает seed)
CREATE POLICY vehicles_tenant_isolated ON vehicles
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- ============================================================================
-- 5. Trigger для updated_at
-- ============================================================================
CREATE OR REPLACE FUNCTION update_vehicles_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_vehicles_updated ON vehicles;
CREATE TRIGGER trg_vehicles_updated
    BEFORE UPDATE ON vehicles
    FOR EACH ROW
    EXECUTE FUNCTION update_vehicles_timestamp();

-- ============================================================================
-- 6. Node types — узлы техники (полиморфные)
-- ============================================================================
CREATE TABLE IF NOT EXISTS vehicle_nodes (
    id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    vehicle_type    vehicle_type   NOT NULL,
    node_code       VARCHAR(50)    NOT NULL,           -- ENGINE, MANUAL_TRANSMISSION, ...
    node_label      VARCHAR(100)   NOT NULL,           -- "Двигатель"
    category_group  VARCHAR(50)    NOT NULL,           -- engine|transmission|drivetrain|fluids|brakes|steering|suspension|hydraulic|other
    icon_name       VARCHAR(50),                       -- для UI: lucide icon name
    display_order   INTEGER        NOT NULL DEFAULT 0,
    is_active       BOOLEAN        NOT NULL DEFAULT true,

    UNIQUE (vehicle_type, node_code)
);

-- ============================================================================
-- 7. Seed vehicle_nodes для всех типов техники
-- ============================================================================
-- 7.1. Легковые авто (9 узлов — совпадает с текущим enum + подвеска)
INSERT INTO vehicle_nodes (vehicle_type, node_code, node_label, category_group, icon_name, display_order) VALUES
    ('passenger_car', 'ENGINE',              'Двигатель',                'engine',       'engine',        1),
    ('passenger_car', 'MANUAL_TRANSMISSION', 'Механическая КПП',         'transmission', 'settings-2',    2),
    ('passenger_car', 'AUTO_TRANSMISSION',   'Автоматическая КПП',       'transmission', 'settings-2',    3),
    ('passenger_car', 'CVT',                 'Вариатор',                 'transmission', 'settings-2',    4),
    ('passenger_car', 'DIFFERENTIAL',        'Дифференциал',             'drivetrain',   'circle-dot',    5),
    ('passenger_car', 'TRANSFER_CASE',       'Раздаточная коробка',      'drivetrain',   'git-merge',     6),
    ('passenger_car', 'COOLANT',             'Система охлаждения',       'fluids',       'droplets',      7),
    ('passenger_car', 'BRAKE',               'Тормозная система',        'brakes',       'disc',          8),
    ('passenger_car', 'STEERING',            'Усилитель руля',           'steering',     'steering',      9),
    ('passenger_car', 'SUSPENSION',          'Подвеска',                 'suspension',   'move',          10)
ON CONFLICT (vehicle_type, node_code) DO NOTHING;

-- 7.2. Тяжёлая техника (специфичные узлы)
INSERT INTO vehicle_nodes (vehicle_type, node_code, node_label, category_group, icon_name, display_order) VALUES
    ('heavy_equipment', 'ENGINE',              'Двигатель',                'engine',       'engine',        1),
    ('heavy_equipment', 'MANUAL_TRANSMISSION', 'Механическая КПП',         'transmission', 'settings-2',    2),
    ('heavy_equipment', 'AUTO_TRANSMISSION',   'Автоматическая КПП',       'transmission', 'settings-2',    3),
    ('heavy_equipment', 'TORQUE_CONVERTER',    'Гидротрансформатор',       'transmission', 'circle',        4),
    ('heavy_equipment', 'HYDRAULIC_SYSTEM',    'Гидравлическая система',   'hydraulic',    'waves',         5),
    ('heavy_equipment', 'FINAL_DRIVE',         'Бортовой редуктор',        'drivetrain',   'git-merge',     6),
    ('heavy_equipment', 'SWING_GEAR',          'Поворотный механизм',      'drivetrain',   'rotate-cw',     7),
    ('heavy_equipment', 'AXLE_DIFFERENTIAL',   'Мостовой дифференциал',    'drivetrain',   'circle-dot',    8),
    ('heavy_equipment', 'COOLANT',             'Система охлаждения',       'fluids',       'droplets',      9),
    ('heavy_equipment', 'BRAKE',               'Тормозная система',        'brakes',       'disc',          10),
    ('heavy_equipment', 'PTO',                 'Отбор мощности (ВОМ)',     'other',        'power',         11),
    ('heavy_equipment', 'GREASE',              'Консистентная смазка',     'fluids',       'droplet',       12)
ON CONFLICT (vehicle_type, node_code) DO NOTHING;

-- 7.3. Грузовики
INSERT INTO vehicle_nodes (vehicle_type, node_code, node_label, category_group, icon_name, display_order) VALUES
    ('heavy_truck', 'ENGINE',              'Двигатель',                'engine',       'engine',        1),
    ('heavy_truck', 'MANUAL_TRANSMISSION', 'Механическая КПП',         'transmission', 'settings-2',    2),
    ('heavy_truck', 'AUTO_TRANSMISSION',   'Автоматическая КПП',       'transmission', 'settings-2',    3),
    ('heavy_truck', 'DIFFERENTIAL',        'Дифференциал',             'drivetrain',   'circle-dot',    4),
    ('heavy_truck', 'TRANSFER_CASE',       'Раздаточная коробка',      'drivetrain',   'git-merge',     5),
    ('heavy_truck', 'WHEEL_HUB',           'Ступица колеса',           'drivetrain',   'circle',        6),
    ('heavy_truck', 'COOLANT',             'Система охлаждения',       'fluids',       'droplets',      7),
    ('heavy_truck', 'BRAKE',               'Тормозная система (пневмо)', 'brakes',     'disc',          8),
    ('heavy_truck', 'STEERING',            'ГУР',                      'steering',     'steering',      9),
    ('heavy_truck', 'PTO',                 'Отбор мощности',           'other',        'power',         10),
    ('heavy_truck', 'ADBLUE',              'AdBlue (SCR)',             'fluids',       'flask-conical', 11)
ON CONFLICT (vehicle_type, node_code) DO NOTHING;

-- 7.4. Мотоциклы
INSERT INTO vehicle_nodes (vehicle_type, node_code, node_label, category_group, icon_name, display_order) VALUES
    ('motorcycle', 'ENGINE',              'Двигатель',                'engine',       'engine',        1),
    ('motorcycle', 'MANUAL_TRANSMISSION', 'КПП',                      'transmission', 'settings-2',    2),
    ('motorcycle', 'CHAIN_DRIVE',         'Цепь привода',             'drivetrain',   'link',          3),
    ('motorcycle', 'SHAFT_DRIVE',         'Карданный вал',            'drivetrain',   'git-merge',     4),
    ('motorcycle', 'COOLANT',             'Система охлаждения',       'fluids',       'droplets',      5),
    ('motorcycle', 'BRAKE',               'Тормозная система',        'brakes',       'disc',          6),
    ('motorcycle', 'FORK_OIL',            'Масло вилки',              'suspension',   'move',          7)
ON CONFLICT (vehicle_type, node_code) DO NOTHING;

-- 7.5. Бензопилы / газонокосилки / малая техника
INSERT INTO vehicle_nodes (vehicle_type, node_code, node_label, category_group, icon_name, display_order) VALUES
    ('small_engine', 'ENGINE',           'Двигатель (2-тактный)',    'engine',   'engine',     1),
    ('small_engine', 'FUEL_MIX',         'Топливная смесь',          'fluids',   'flask',      2),
    ('small_engine', 'BAR_LUBRICATION',  'Смазка шины и цепи',       'other',    'link',       3),
    ('small_engine', 'AIR_FILTER_OIL',   'Масло воздушного фильтра', 'fluids',   'wind',       4),
    ('small_engine', 'GREASE',           'Консистентная смазка',     'fluids',   'droplet',    5)
ON CONFLICT (vehicle_type, node_code) DO NOTHING;

-- ============================================================================
-- 8. Fluids — таблица масел/жидкостей (без изменений, но с расширенными типами)
-- ============================================================================
-- Уже существует в текущей схеме, расширяем fluid_type enum:
DO $$ BEGIN
    ALTER TYPE fluid_type ADD VALUE IF NOT EXISTS 'grease';
    ALTER TYPE fluid_type ADD VALUE IF NOT EXISTS 'adblue';
    ALTER TYPE fluid_type ADD VALUE IF NOT EXISTS 'fuel_mix';
    ALTER TYPE fluid_type ADD VALUE IF NOT EXISTS 'bar_oil';
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- ============================================================================
-- 9. Recommendations — с поддержкой ранга (основное / альтернатива)
-- ============================================================================
-- Теперь одна и та же пара (vehicle, node) может иметь несколько масел
-- с разным рангом (1 = primary, 2 = alt1, 3 = alt2)
-- Это позволяет поддержать PVL-формат с "рекомендованным + альтернативой"

CREATE TABLE IF NOT EXISTS vehicle_recommendations (
    id                      UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID           NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'::uuid,
    vehicle_id              UUID           NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
    node_code               VARCHAR(50)    NOT NULL,

    -- Жидкость
    fluid_id                UUID           REFERENCES fluids(id) ON DELETE SET NULL,
    fluid_name_override     VARCHAR(300),  -- если fluid не найден в справочнике, храним имя тут

    -- Ранг рекомендации (1 = основное, 2 = первая альтернатива, 3 = вторая альтернатива)
    recommendation_rank     SMALLINT       NOT NULL DEFAULT 1,
    is_oem_recommendation   BOOLEAN        NOT NULL DEFAULT false,

    -- Объём (текст, потому что в каталогах встречается "0.8-1.2", "<", "1-1,5")
    volume_liters           VARCHAR(50),
    volume_with_filter      VARCHAR(50),

    -- Условия применимости (для подмоделей: Diesel, с кондиционером, и т.д.)
    applicability_conditions JSONB         DEFAULT '{}'::jsonb,
    -- Примеры: {"fuel_type": "diesel", "transmission": "manual", "has_ac": true, "marker_code": "u"}

    -- Дополнительные пометки
    oem_specification       VARCHAR(200),
    notes                   TEXT,
    source                  VARCHAR(50),   -- 'japan_catalog', 'pvl', 'manual'

    -- Метаданные
    is_published            BOOLEAN        NOT NULL DEFAULT true,
    confidence_score        FLOAT          DEFAULT 0.8,
    created_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    -- Один fluid на один узел одного авто с одним рангом
    CONSTRAINT vehicle_recs_unique
        UNIQUE (vehicle_id, node_code, fluid_id, recommendation_rank)
);

CREATE INDEX IF NOT EXISTS idx_vehicle_recs_vehicle_node
    ON vehicle_recommendations (vehicle_id, node_code, recommendation_rank);

CREATE INDEX IF NOT EXISTS idx_vehicle_recs_tenant
    ON vehicle_recommendations (tenant_id);

CREATE INDEX IF NOT EXISTS idx_vehicle_recs_node
    ON vehicle_recommendations (node_code);

CREATE INDEX IF NOT EXISTS idx_vehicle_recs_conditions_gin
    ON vehicle_recommendations USING gin (applicability_conditions);

-- ============================================================================
-- 10. RLS для recommendations
-- ============================================================================
ALTER TABLE vehicle_recommendations ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicle_recommendations FORCE ROW LEVEL SECURITY;

CREATE POLICY vehicle_recs_tenant ON vehicle_recommendations
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

CREATE OR REPLACE FUNCTION update_vehicle_recs_timestamp()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_vehicle_recs_updated ON vehicle_recommendations;
CREATE TRIGGER trg_vehicle_recs_updated
    BEFORE UPDATE ON vehicle_recommendations
    FOR EACH ROW EXECUTE FUNCTION update_vehicle_recs_timestamp();

-- ============================================================================
-- 11. Backward compatibility — view для старого API
-- ============================================================================
-- Старая таблица car_variants остаётся нетронутой, но все новые данные пишем в vehicles.
-- Для единообразного API создаём view:

CREATE OR REPLACE VIEW car_variants_unified AS
SELECT
    v.id,
    v.tenant_id,
    v.brand,
    v.model,
    v.generation,
    v.year_start,
    v.year_end,
    v.market,
    v.attributes->>'engine_code'         AS engine_code,
    v.attributes->>'displacement_liters' AS displacement_liters,
    v.attributes->>'fuel_type'           AS fuel_type,
    v.attributes->>'drive_type'          AS drive_type,
    v.attributes->>'transmission_type'   AS transmission_type,
    v.attributes->>'body_number'         AS body_number,
    v.attributes->>'body_style'          AS body_style,
    v.source_hash,
    v.is_published,
    v.created_at,
    v.updated_at
FROM vehicles v
WHERE v.vehicle_type = 'passenger_car';

-- ============================================================================
-- 12. Helper functions
-- ============================================================================

-- Поиск транспортных средств по параметрам (полиморфный)
CREATE OR REPLACE FUNCTION search_vehicles(
    p_vehicle_type  vehicle_type,
    p_brand         VARCHAR DEFAULT NULL,
    p_model         VARCHAR DEFAULT NULL,
    p_year          INTEGER DEFAULT NULL,
    p_engine_code   VARCHAR DEFAULT NULL,
    p_market        VARCHAR DEFAULT NULL,
    p_limit         INTEGER DEFAULT 50
) RETURNS TABLE (
    id UUID,
    brand VARCHAR,
    model VARCHAR,
    generation VARCHAR,
    sub_model VARCHAR,
    year_start INTEGER,
    year_end INTEGER,
    attributes JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        v.id, v.brand, v.model, v.generation, v.sub_model,
        v.year_start, v.year_end, v.attributes
    FROM vehicles v
    WHERE v.vehicle_type = p_vehicle_type
      AND v.is_published = true
      AND v.needs_review = false
      AND (p_brand IS NULL OR v.brand ILIKE '%' || p_brand || '%')
      AND (p_model IS NULL OR v.model ILIKE '%' || p_model || '%')
      AND (p_market IS NULL OR v.market = p_market)
      AND (p_year IS NULL OR (v.year_start <= p_year AND (v.year_end IS NULL OR v.year_end >= p_year)))
      AND (p_engine_code IS NULL OR v.attributes->>'engine_code' = p_engine_code)
    ORDER BY v.brand, v.model, v.year_start
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Получить все рекомендации для авто + узла
CREATE OR REPLACE FUNCTION get_recommendations_for_vehicle(
    p_vehicle_id UUID,
    p_node_code  VARCHAR DEFAULT NULL
) RETURNS TABLE (
    node_code VARCHAR,
    node_label VARCHAR,
    fluid_id UUID,
    fluid_name VARCHAR,
    fluid_brand VARCHAR,
    viscosity_sae VARCHAR,
    recommendation_rank SMALLINT,
    is_oem BOOLEAN,
    volume_liters VARCHAR,
    applicability_conditions JSONB
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        r.node_code,
        vn.node_label,
        r.fluid_id,
        COALESCE(f.canonical_name, r.fluid_name_override) AS fluid_name,
        f.brand AS fluid_brand,
        f.viscosity_sae,
        r.recommendation_rank,
        r.is_oem_recommendation,
        r.volume_liters,
        r.applicability_conditions
    FROM vehicle_recommendations r
    LEFT JOIN fluids f ON f.id = r.fluid_id
    LEFT JOIN vehicle_nodes vn ON vn.vehicle_type = (
        SELECT vehicle_type FROM vehicles WHERE id = p_vehicle_id
    ) AND vn.node_code = r.node_code
    WHERE r.vehicle_id = p_vehicle_id
      AND r.is_published = true
      AND (p_node_code IS NULL OR r.node_code = p_node_code)
    ORDER BY r.node_code, r.recommendation_rank;
END;
$$ LANGUAGE plpgsql STABLE;
