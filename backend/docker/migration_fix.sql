-- =============================================================
-- migration_fix.sql — Составные UNIQUE constraints с company_id
-- =============================================================

-- 1. car_variants: удаляем глобальный UNIQUE(source_hash), создаём составной
ALTER TABLE car_variants DROP CONSTRAINT IF EXISTS car_variants_source_hash_key;
CREATE UNIQUE INDEX idx_car_variants_company_source_hash
    ON car_variants(company_id, source_hash) WHERE source_hash IS NOT NULL;

-- 2. fluids: удаляем глобальный UNIQUE(hash_signature), создаём составной
ALTER TABLE fluids DROP CONSTRAINT IF EXISTS fluids_hash_signature_key;
CREATE UNIQUE INDEX idx_fluids_company_hash_signature
    ON fluids(company_id, hash_signature) WHERE hash_signature IS NOT NULL;
