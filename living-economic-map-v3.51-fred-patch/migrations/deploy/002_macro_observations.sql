CREATE TABLE IF NOT EXISTS macro_series (
    series_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    units TEXT,
    frequency TEXT,
    category TEXT NOT NULL,
    interpretation TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS macro_observations (
    observation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    series_id TEXT NOT NULL REFERENCES macro_series(series_id),
    observation_date DATE NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    realtime_start DATE,
    realtime_end DATE,
    retrieved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(series_id, observation_date, realtime_start)
);

CREATE INDEX IF NOT EXISTS idx_macro_observations_latest
ON macro_observations(series_id, observation_date DESC, retrieved_at DESC);

CREATE TABLE IF NOT EXISTS macro_ingestion_runs (
    ingestion_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    status TEXT NOT NULL,
    series_requested INTEGER NOT NULL DEFAULT 0,
    series_succeeded INTEGER NOT NULL DEFAULT 0,
    observations_written INTEGER NOT NULL DEFAULT 0,
    error_details JSONB NOT NULL DEFAULT '[]'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_macro_ingestion_runs_time
ON macro_ingestion_runs(started_at DESC);
