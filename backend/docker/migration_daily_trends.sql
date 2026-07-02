-- ============================================================================
-- GSM Migration — daily_trends table for predictive analytics
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_trends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    metric TEXT NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (company_id, date, metric)
);

CREATE INDEX IF NOT EXISTS idx_daily_trends_company_date
    ON daily_trends (company_id, date DESC);

-- Enable RLS
ALTER TABLE daily_trends ENABLE ROW LEVEL SECURITY;

-- RLS policies
CREATE POLICY daily_trends_tenant ON daily_trends
    USING (company_id = (current_setting('app.tenant_id', true))::uuid)
    WITH CHECK (company_id = (current_setting('app.tenant_id', true))::uuid);
