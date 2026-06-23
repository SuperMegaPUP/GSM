-- ============================================================================
-- GSM Sales Copilot — Objection Cases Table
-- Migration: 00XX_objection_cases.sql
-- ============================================================================

-- 1. Categories enum
DO $$ BEGIN
    CREATE TYPE objection_category AS ENUM (
        'price',         -- Ценовые возражения
        'quality',       -- Качество и технические характеристики
        'logistics',     -- Логистика и сроки
        'service',       -- Работа с поставщиком и сервис
        'brand',         -- Бренд и лояльность
        'business',      -- Специфика бизнеса клиента
        'closing'        -- Финальные сомнения и отказы
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 2. Main table
CREATE TABLE IF NOT EXISTS objection_cases (
    id              VARCHAR(32)    PRIMARY KEY,
    tenant_id       UUID           NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'::uuid,
    number          INTEGER,
    category        objection_category NOT NULL,
    category_label  VARCHAR(100)   NOT NULL,
    objection_text  TEXT           NOT NULL,
    response_text   TEXT           NOT NULL,
    tags            VARCHAR(50)[]  NOT NULL DEFAULT '{}',
    content_hash    VARCHAR(16)    NOT NULL,
    -- Metadata
    is_seed         BOOLEAN        NOT NULL DEFAULT false,  -- true для заводских кейсов
    is_published    BOOLEAN        NOT NULL DEFAULT true,   -- скрытые технологом не индексируются
    -- Quality (for RLHF — review feedback)
    quality_score   FLOAT          DEFAULT 0.5,  -- 0..1, 0.5 = нейтрально
    usage_count     INTEGER        NOT NULL DEFAULT 0,      -- сколько раз кейс использовался в подсказке
    last_used_at    TIMESTAMPTZ,
    -- Context (опционально — для специализации)
    car_brand       VARCHAR(50),   -- если кейс специфичен для бренда авто
    car_model       VARCHAR(50),
    fluid_type      VARCHAR(50),   -- если кейс специфичен для типа масла
    -- Vector embedding reference (stored in Qdrant)
    qdrant_point_id UUID,          -- ID точки в Qdrant для поиска/удаления
    -- Timestamps
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    created_by      UUID           REFERENCES users(id) ON DELETE SET NULL,

    -- Constraints
    CONSTRAINT objection_cases_hash_unique UNIQUE (tenant_id, content_hash)
);

-- 3. Indexes
CREATE INDEX IF NOT EXISTS idx_objection_cases_tenant
    ON objection_cases (tenant_id);

CREATE INDEX IF NOT EXISTS idx_objection_cases_category
    ON objection_cases (tenant_id, category);

CREATE INDEX IF NOT EXISTS idx_objection_cases_published
    ON objection_cases (tenant_id, is_published)
    WHERE is_published = true;

-- Full-text search by objection text (fallback for when Qdrant is down)
CREATE INDEX IF NOT EXISTS idx_objection_cases_text_fts
    ON objection_cases USING gin (
        to_tsvector('russian', objection_text || ' ' || response_text)
    );

-- Tags GIN index for tag-based filtering
CREATE INDEX IF NOT EXISTS idx_objection_cases_tags
    ON objection_cases USING gin (tags);

-- 4. Row-Level Security (multi-tenant isolation)
ALTER TABLE objection_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE objection_cases FORCE ROW LEVEL SECURITY;

-- Seed cases (is_seed=true, tenant_id=00000000-...) — доступны ВСЕМ тенантам
CREATE POLICY objection_cases_seed_global ON objection_cases
    FOR SELECT
    USING (is_seed = true);

-- Tenant-specific cases — только владелец
CREATE POLICY objection_cases_tenant_isolated ON objection_cases
    FOR ALL
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

-- 5. Trigger для updated_at
CREATE OR REPLACE FUNCTION update_objection_cases_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_objection_cases_updated ON objection_cases;
CREATE TRIGGER trg_objection_cases_updated
    BEFORE UPDATE ON objection_cases
    FOR EACH ROW
    EXECUTE FUNCTION update_objection_cases_timestamp();

-- 6. Increment usage_count helper (called by Sales Copilot service)
CREATE OR REPLACE FUNCTION increment_objection_case_usage(
    p_case_id VARCHAR,
    p_tenant_id UUID
) RETURNS VOID AS $$
BEGIN
    UPDATE objection_cases
    SET usage_count = usage_count + 1,
        last_used_at = NOW()
    WHERE id = p_case_id
      AND (tenant_id = p_tenant_id OR is_seed = true);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Qdrant collection (выполнить в Qdrant REST API, НЕ в PostgreSQL)
-- ============================================================================
--
-- POST http://qdrant:6333/collections/sales_objections
-- {
--   "vectors": {
--     "size": 384,
--     "distance": "Cosine"
--   },
--   "optimizers_config": {
--     "default_segment_number": 2,
--     "indexing_threshold": 20000
--   },
--   "on_disk_payload": true,
--   "payload_schema": {
--     "case_id":         { "type": "keyword" },
--     "tenant_id":       { "type": "keyword" },
--     "category":        { "type": "keyword" },
--     "category_label":  { "type": "keyword" },
--     "objection_text":  { "type": "text" },
--     "response_text":   { "type": "text" },
--     "tags":            { "type": "keyword[]" },
--     "is_seed":         { "type": "bool" },
--     "is_published":    { "type": "bool" },
--     "car_brand":       { "type": "keyword" },
--     "fluid_type":      { "type": "keyword" },
--     "usage_count":     { "type": "integer" },
--     "quality_score":   { "type": "float" },
--     "created_at":      { "type": "datetime" }
--   }
-- }
-- ============================================================================

-- ============================================================================
-- Seed data: load 100 cases
-- Run: psql -d gsm -f objection_cases.sql (after this migration)
-- ============================================================================
