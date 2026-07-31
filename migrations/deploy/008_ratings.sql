CREATE TABLE IF NOT EXISTS ratings_snapshot (
    benzinga_id TEXT,
    ticker TEXT,
    company_name TEXT,
    rating_date DATE,
    action_company TEXT,
    action_pt TEXT,
    rating_current TEXT,
    rating_prior TEXT,
    pt_current NUMERIC,
    pt_prior NUMERIC,
    analyst_name TEXT,
    analyst_firm TEXT,
    importance INTEGER,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ratings_snapshot_date ON ratings_snapshot(rating_date DESC);
