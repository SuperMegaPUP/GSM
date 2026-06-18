-- =============================================================
-- init.sql — Инициализация БД Oil Expert SaaS MVP
-- Расширения, ENUM-типы, таблицы с RLS, индексы, seed-данные
-- =============================================================

-- 1. Расширения
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. ENUM-типы
CREATE TYPE user_role AS ENUM ('admin', 'supervisor', 'manager', 'technologist');
CREATE TYPE fluid_type AS ENUM (
    'engine_oil', 'manual_transmission', 'auto_transmission',
    'cvt', 'differential', 'transfer_case',
    'steering', 'brake', 'coolant'
);
CREATE TYPE node_type AS ENUM (
    'ENGINE', 'MANUAL_TRANSMISSION', 'AUTO_TRANSMISSION',
    'CVT', 'TRANSFER_CASE', 'FRONT_DIFF', 'REAR_DIFF',
    'STEERING', 'BRAKE', 'COOLANT'
);
CREATE TYPE subscription_status AS ENUM (
    'active', 'grace_period', 'suspended', 'blocked'
);
CREATE TYPE import_status AS ENUM (
    'pending', 'processing', 'review', 'completed', 'failed'
);

-- 3. Таблицы

-- 3.1 Компании (тенанты)
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    subscription_status subscription_status NOT NULL DEFAULT 'active',
    grace_period_ends_at TIMESTAMPTZ,
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3.2 Пользователи
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL DEFAULT '',
    role user_role NOT NULL DEFAULT 'manager',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- 3.3 Марки автомобилей
CREATE TABLE car_brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name_ru VARCHAR(100) NOT NULL,
    name_en VARCHAR(100),
    country VARCHAR(100),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(name_ru, company_id)
);
ALTER TABLE car_brands ENABLE ROW LEVEL SECURITY;

-- 3.4 Модели автомобилей
CREATE TABLE car_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_id UUID NOT NULL REFERENCES car_brands(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    generation VARCHAR(100),
    year_start INTEGER,
    year_end INTEGER,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(brand_id, name, generation, company_id)
);
ALTER TABLE car_models ENABLE ROW LEVEL SECURITY;

-- 3.5 Варианты автомобилей (конкретная модификация)
CREATE TABLE car_variants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID NOT NULL REFERENCES car_models(id) ON DELETE CASCADE,
    engine_code VARCHAR(50),
    engine_volume NUMERIC(3,1),
    fuel_type VARCHAR(20),
    body_type VARCHAR(50),
    drive_type VARCHAR(20),
    transmission_type VARCHAR(20),
    year_start INTEGER,
    year_end INTEGER,
    source_hash VARCHAR(64) UNIQUE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE car_variants ENABLE ROW LEVEL SECURITY;

-- 3.6 Жидкости / масла
CREATE TABLE fluids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_name VARCHAR(255) NOT NULL,
    brand VARCHAR(100),
    product_line VARCHAR(100),
    viscosity_sae VARCHAR(20),
    api_class VARCHAR(20),
    acea_class VARCHAR(20),
    oem_approvals JSONB NOT NULL DEFAULT '[]',
    fluid_type fluid_type NOT NULL DEFAULT 'engine_oil',
    hash_signature VARCHAR(64) UNIQUE,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(canonical_name, company_id)
);
ALTER TABLE fluids ENABLE ROW LEVEL SECURITY;

-- 3.7 Рекомендации (связка вариант + узел + жидкость)
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    car_variant_id UUID NOT NULL REFERENCES car_variants(id) ON DELETE CASCADE,
    node_type node_type NOT NULL,
    fluid_id UUID NOT NULL REFERENCES fluids(id) ON DELETE CASCADE,
    volume_liters NUMERIC(5,2),
    volume_with_filter NUMERIC(5,2),
    is_oem_recommendation BOOLEAN NOT NULL DEFAULT false,
    oem_specification VARCHAR(100),
    confidence_score NUMERIC(3,2),
    source VARCHAR(100),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE recommendations ENABLE ROW LEVEL SECURITY;

-- 3.8 Журнал импортов
CREATE TABLE import_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    uploaded_by UUID REFERENCES users(id),
    status import_status NOT NULL DEFAULT 'pending',
    total_rows INTEGER NOT NULL DEFAULT 0,
    new_rows INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    errors INTEGER NOT NULL DEFAULT 0,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE import_batches ENABLE ROW LEVEL SECURITY;

-- 3.9 Staging-таблица для сырых данных (до модерации технологом)
CREATE TABLE staging_rows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
    raw_data JSONB NOT NULL,
    parsed_data JSONB,
    validation_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    duplicate_of UUID,
    error_message TEXT,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE staging_rows ENABLE ROW LEVEL SECURITY;

-- 4. Политики Row-Level Security

-- Пользователи: менеджеры видят только пользователей своей компании
CREATE POLICY tenant_isolation_users ON users
    USING (company_id = current_setting('app.current_tenant_id')::uuid);

-- Марки: изоляция по компании
CREATE POLICY tenant_isolation_car_brands ON car_brands
    USING (company_id = current_setting('app.current_tenant_id')::uuid);

-- Модели: изоляция по компании
CREATE POLICY tenant_isolation_car_models ON car_models
    USING (company_id = current_setting('app.current_tenant_id')::uuid);

-- Варианты: изоляция по компании
CREATE POLICY tenant_isolation_car_variants ON car_variants
    USING (company_id = current_setting('app.current_tenant_id')::uuid);

-- Жидкости: изоляция по компании
CREATE POLICY tenant_isolation_fluids ON fluids
    USING (company_id = current_setting('app.current_tenant_id')::uuid);

-- Рекомендации: изоляция по компании
CREATE POLICY tenant_isolation_recommendations ON recommendations
    USING (company_id = current_setting('app.current_tenant_id')::uuid);

-- Импорты: изоляция по компании
CREATE POLICY tenant_isolation_import_batches ON import_batches
    USING (company_id = current_setting('app.current_tenant_id')::uuid);

-- Строки импорта: изоляция по компании
CREATE POLICY tenant_isolation_staging_rows ON staging_rows
    USING (company_id = current_setting('app.current_tenant_id')::uuid);

-- 5. Индексы

-- Пользователи
CREATE INDEX idx_users_company ON users(company_id);
CREATE INDEX idx_users_email ON users(email);

-- Марки
CREATE INDEX idx_brands_name ON car_brands USING gin (name_ru gin_trgm_ops);
CREATE INDEX idx_brands_company ON car_brands(company_id);

-- Модели
CREATE INDEX idx_models_brand ON car_models(brand_id);
CREATE INDEX idx_models_name ON car_models USING gin (name gin_trgm_ops);
CREATE INDEX idx_models_company ON car_models(company_id);

-- Варианты
CREATE INDEX idx_variants_model ON car_variants(model_id);
CREATE INDEX idx_variants_engine ON car_variants(engine_code);
CREATE INDEX idx_variants_source_hash ON car_variants(source_hash);
CREATE INDEX idx_variants_years ON car_variants(year_start, year_end);
CREATE INDEX idx_variants_company ON car_variants(company_id);

-- Жидкости
CREATE INDEX idx_fluids_canonical ON fluids(canonical_name);
CREATE INDEX idx_fluids_hash ON fluids(hash_signature);
CREATE INDEX idx_fluids_type ON fluids(fluid_type);
CREATE INDEX idx_fluids_oem ON fluids USING gin (oem_approvals);
CREATE INDEX idx_fluids_company ON fluids(company_id);

-- Рекомендации
CREATE INDEX idx_recommendations_variant ON recommendations(car_variant_id);
CREATE INDEX idx_recommendations_fluid ON recommendations(fluid_id);
CREATE INDEX idx_recommendations_oem ON recommendations(is_oem_recommendation);
CREATE INDEX idx_recommendations_company ON recommendations(company_id);

-- Импорты
CREATE INDEX idx_imports_company ON import_batches(company_id);
CREATE INDEX idx_imports_status ON import_batches(status);

-- 6. Функция для автообновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггеры updated_at для всех таблиц
CREATE TRIGGER trg_companies_updated_at
    BEFORE UPDATE ON companies FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_car_brands_updated_at
    BEFORE UPDATE ON car_brands FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_car_models_updated_at
    BEFORE UPDATE ON car_models FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_car_variants_updated_at
    BEFORE UPDATE ON car_variants FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_fluids_updated_at
    BEFORE UPDATE ON fluids FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_recommendations_updated_at
    BEFORE UPDATE ON recommendations FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_import_batches_updated_at
    BEFORE UPDATE ON import_batches FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_staging_rows_updated_at
    BEFORE UPDATE ON staging_rows FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 7. Seed-данные

-- Создаём административную компанию
INSERT INTO companies (id, name, subscription_status) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Super Admin', 'active');

-- Создаём администратора (пароль: admin123)
-- Хэш сгенерирован через passlib bcrypt
INSERT INTO users (id, company_id, email, hashed_password, full_name, role) VALUES
    (
        '00000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001',
        'admin@oil-expert.ru',
        '$2b$12$Yl80no9IvJL49PvnUFJem.8gRp4Kok5nICd59c.O/IjqOTZmpAVVq',
        'Admin',
        'admin'
    );
