-- ============================================================================
-- GSM Sales Copilot 2.0 — Objection Cases (UPGRADED SCHEMA)
-- ============================================================================
-- Incorporates:
--   - Original schema (RLS, tags, content_hash, qdrant_point_id)
--   - Qwen's good ideas: arguments[], customer_segment, outcome, success_count/failure_count
--   - Hybrid search support: separate FTS index + Qdrant vector
--   - Named vectors in Qdrant: objection_vector + response_vector
--   - Temporal decay: last_used_at for "freshness" scoring
-- ============================================================================

-- 1. Categories enum (7 categories from the source file)
DO $$ BEGIN
    CREATE TYPE objection_category AS ENUM (
        'price',         -- Ценовые возражения (20 кейсов)
        'quality',       -- Качество и технические характеристики (20)
        'logistics',     -- Логистика и сроки (15)
        'service',       -- Работа с поставщиком и сервис (15)
        'brand',         -- Бренд и лояльность (10)
        'business',      -- Специфика бизнеса клиента (10)
        'closing'        -- Финальные сомнения и отказы (10)
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 2. Outcome enum (for RLHF)
DO $$ BEGIN
    CREATE TYPE objection_outcome AS ENUM (
        'pending',       -- кейс ещё не использовался
        'closed_won',    -- сработал, клиент согласился
        'closed_lost'    -- не сработал, клиент отказался
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 3. Customer segment enum (for filtering by client type)
DO $$ BEGIN
    CREATE TYPE customer_segment AS ENUM (
        'b2b_fleet',         -- автопарк / логистика
        'b2c_retail',        -- розничный покупатель
        'service_station',   -- СТО / автосервис
        'distributor',       -- дистрибьютор / оптовик
        'government',        -- госзаказчик
        'universal'          -- кейс универсален (по умолчанию)
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 4. Main table
CREATE TABLE IF NOT EXISTS objection_cases (
    id              VARCHAR(32)    PRIMARY KEY,
    tenant_id       UUID           NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000'::uuid,

    -- Classification
    number          INTEGER,                          -- порядковый номер (для seed-кейсов)
    category        objection_category NOT NULL,
    category_label  VARCHAR(100)   NOT NULL,           -- "Ценовые возражения"
    customer_segment customer_segment NOT NULL DEFAULT 'universal',

    -- Content (Qwen's richer structure)
    objection_text  TEXT           NOT NULL,
    response_text   TEXT           NOT NULL,
    arguments       JSONB          NOT NULL DEFAULT '[]'::jsonb,  -- список ключевых аргументов
    product_context JSONB          DEFAULT '{}'::jsonb,           -- {brand, product, viscosity, api}
    tags            VARCHAR(50)[]  NOT NULL DEFAULT '{}',

    -- Outcome & RLHF (replaces single quality_score)
    outcome         objection_outcome NOT NULL DEFAULT 'pending',
    usage_count     INTEGER        NOT NULL DEFAULT 0,
    success_count   INTEGER        NOT NULL DEFAULT 0,
    failure_count   INTEGER        NOT NULL DEFAULT 0,
    last_used_at    TIMESTAMPTZ,

    -- Lifecycle
    is_seed         BOOLEAN        NOT NULL DEFAULT false,  -- true для заводских кейсов
    is_published    BOOLEAN        NOT NULL DEFAULT true,
    source          VARCHAR(20)    NOT NULL DEFAULT 'seed', -- seed | manual | feedback | import
    needs_review    BOOLEAN        NOT NULL DEFAULT false,  -- true если quality упал ниже порога

    -- Context specialization
    car_brand       VARCHAR(50),
    car_model       VARCHAR(50),
    fluid_type      VARCHAR(50),

    -- Vector storage references (Qdrant)
    qdrant_point_id UUID,                                  -- single point with named vectors

    -- Hash for deduplication
    content_hash    VARCHAR(16)    NOT NULL,

    -- Timestamps
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    created_by      UUID           REFERENCES users(id) ON DELETE SET NULL,

    -- Constraints
    CONSTRAINT objection_cases_hash_unique UNIQUE (tenant_id, content_hash),
    CONSTRAINT objection_cases_success_check
        CHECK (success_count <= usage_count)
);

-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_objection_cases_tenant
    ON objection_cases (tenant_id);

CREATE INDEX IF NOT EXISTS idx_objection_cases_category
    ON objection_cases (tenant_id, category);

CREATE INDEX IF NOT EXISTS idx_objection_cases_segment
    ON objection_cases (tenant_id, customer_segment);

CREATE INDEX IF NOT EXISTS idx_objection_cases_published
    ON objection_cases (tenant_id, is_published, needs_review)
    WHERE is_published = true AND needs_review = false;

-- Full-text search by objection + arguments (for hybrid search BM25 leg)
CREATE INDEX IF NOT EXISTS idx_objection_cases_fts
    ON objection_cases USING gin (
        to_tsvector('russian',
            objection_text || ' ' ||
            coalesce(array_to_string(arguments, ' '), '') || ' ' ||
            response_text
        )
    );

-- Tags GIN index
CREATE INDEX IF NOT EXISTS idx_objection_cases_tags
    ON objection_cases USING gin (tags);

-- Last-used index for temporal decay calculations
CREATE INDEX IF NOT EXISTS idx_objection_cases_last_used
    ON objection_cases (last_used_at DESC)
    WHERE last_used_at IS NOT NULL;

-- 6. Computed success_rate (function, not column — always fresh)
CREATE OR REPLACE FUNCTION objection_case_success_rate(case_row objection_cases)
RETURNS FLOAT AS $$
DECLARE
    total INTEGER;
BEGIN
    total := case_row.success_count + case_row.failure_count;
    IF total = 0 THEN
        RETURN 0.5;  -- neutral start
    END IF;
    RETURN case_row.success_count::FLOAT / total;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 7. Temporal-decay-aware score (for ranking)
-- Combines success_rate × log(usage) × freshness decay
CREATE OR REPLACE FUNCTION objection_case_effective_score(
    p_success_count INTEGER,
    p_failure_count INTEGER,
    p_usage_count   INTEGER,
    p_last_used_at  TIMESTAMPTZ
) RETURNS FLOAT AS $$
DECLARE
    total       INTEGER;
    success_rate FLOAT;
    usage_factor FLOAT;
    freshness   FLOAT;
    days_since  INTEGER;
BEGIN
    total := p_success_count + p_failure_count;
    IF total = 0 THEN
        RETURN 0.4;  -- neutral start for new cases
    END IF;
    success_rate := p_success_count::FLOAT / total;
    usage_factor := log(1 + p_usage_count) / log(1 + 50);  -- normalize to [0..1] at 50 uses
    -- Temporal decay: half-life 90 days
    IF p_last_used_at IS NULL THEN
        freshness := 0.5;
    ELSE
        days_since := EXTRACT(DAY FROM NOW() - p_last_used_at)::INTEGER;
        freshness := exp(-days_since::FLOAT / 90.0);
    END IF;
    -- Weighted combination
    RETURN (success_rate * 0.6) + (usage_factor * 0.2) + (freshness * 0.2);
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 8. Row-Level Security (multi-tenant isolation)
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

-- 9. Trigger для updated_at
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

-- 10. Auto-flag for review when quality drops below threshold
CREATE OR REPLACE FUNCTION check_objection_case_quality()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.failure_count >= 3 AND NEW.success_count::FLOAT / (NEW.success_count + NEW.failure_count) < 0.3 THEN
        NEW.needs_review := true;
        NEW.is_published := false;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_objection_case_quality ON objection_cases;
CREATE TRIGGER trg_objection_case_quality
    AFTER INSERT OR UPDATE OF success_count, failure_count ON objection_cases
    FOR EACH ROW
    EXECUTE FUNCTION check_objection_case_quality();

-- 11. Helper: record feedback (closed_won or closed_lost)
CREATE OR REPLACE FUNCTION record_objection_feedback(
    p_case_id   VARCHAR,
    p_tenant_id UUID,
    p_outcome   objection_outcome,
    p_comment   TEXT DEFAULT NULL
) RETURNS TABLE(success_rate FLOAT, needs_review BOOLEAN) AS $$
DECLARE
    v_case       objection_cases%ROWTYPE;
    v_total      INTEGER;
    v_success    FLOAT;
BEGIN
    -- Lock + update atomically
    SELECT * INTO v_case
    FROM objection_cases
    WHERE id = p_case_id
      AND (is_seed = true OR tenant_id = p_tenant_id)
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Case % not found for tenant %', p_case_id, p_tenant_id;
    END IF;

    UPDATE objection_cases
    SET
        usage_count  = usage_count + 1,
        success_count = CASE WHEN p_outcome = 'closed_won' THEN success_count + 1 ELSE success_count END,
        failure_count = CASE WHEN p_outcome = 'closed_lost' THEN failure_count + 1 ELSE failure_count END,
        outcome       = p_outcome,
        last_used_at  = NOW()
    WHERE id = p_case_id
      AND (is_seed = true OR tenant_id = p_tenant_id)
    RETURNING * INTO v_case;

    v_total := v_case.success_count + v_case.failure_count;
    v_success := CASE WHEN v_total > 0 THEN v_case.success_count::FLOAT / v_total ELSE 0.5 END;

    RETURN QUERY SELECT v_success, v_case.needs_review;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- Qdrant collection with NAMED VECTORS (objection_vector + response_vector)
-- ============================================================================
-- Execute this via Qdrant REST API (NOT in PostgreSQL):
--
-- PUT http://qdrant:6333/collections/sales_objections
-- {
--   "vectors": {
--     "default": {                   # objection_vector — primary search vector
--       "size": 384,
--       "distance": "Cosine"
--     },
--     "response": {                  # response_vector — optional, for finding similar answers
--       "size": 384,
--       "distance": "Cosine"
--     }
--   },
--   "optimizers_config": {
--     "default_segment_number": 2,
--     "indexing_threshold": 20000
--   },
--   "on_disk_payload": true,
--   "payload_schema": {
--     "case_id":           { "type": "keyword" },
--     "tenant_id":         { "type": "keyword" },
--     "category":          { "type": "keyword" },
--     "category_label":    { "type": "keyword" },
--     "customer_segment":  { "type": "keyword" },
--     "objection_text":    { "type": "text" },
--     "response_text":     { "type": "text" },
--     "arguments":         { "type": "keyword[]" },
--     "tags":              { "type": "keyword[]" },
--     "is_seed":           { "type": "bool" },
--     "is_published":      { "type": "bool" },
--     "needs_review":      { "type": "bool" },
--     "outcome":           { "type": "keyword" },
--     "usage_count":       { "type": "integer" },
--     "success_count":     { "type": "integer" },
--     "failure_count":     { "type": "integer" },
--     "car_brand":         { "type": "keyword" },
--     "fluid_type":        { "type": "keyword" },
--     "source":            { "type": "keyword" },
--     "last_used_at":      { "type": "datetime" },
--     "created_at":        { "type": "datetime" }
--   }
-- }
-- ============================================================================
