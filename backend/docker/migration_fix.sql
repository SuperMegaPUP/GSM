-- =============================================================
-- migration_fix.sql — Составные UNIQUE constraints с company_id
-- =============================================================

-- 1. car_variants: удаляем старые ограничения, создаём составное UNIQUE
ALTER TABLE car_variants DROP CONSTRAINT IF EXISTS car_variants_source_hash_key;
ALTER TABLE car_variants DROP CONSTRAINT IF EXISTS car_variants_company_source_hash_key;
DROP INDEX IF EXISTS idx_car_variants_company_source_hash;
ALTER TABLE car_variants ADD CONSTRAINT car_variants_company_source_hash_uq UNIQUE (company_id, source_hash);

-- 2. fluids: удаляем старые ограничения, создаём составное UNIQUE
ALTER TABLE fluids DROP CONSTRAINT IF EXISTS fluids_hash_signature_key;
ALTER TABLE fluids DROP CONSTRAINT IF EXISTS fluids_company_hash_signature_key;
DROP INDEX IF EXISTS idx_fluids_company_hash_signature;
ALTER TABLE fluids ADD CONSTRAINT fluids_company_hash_signature_uq UNIQUE (company_id, hash_signature);

-- 3. recommendations: уникальность по (company_id, car_variant_id, node_type, fluid_id)
CREATE UNIQUE INDEX IF NOT EXISTS uq_recommendations_variant_node_fluid
ON recommendations (company_id, car_variant_id, node_type, fluid_id);
