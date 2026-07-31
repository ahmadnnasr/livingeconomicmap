CREATE TABLE IF NOT EXISTS trending_tickers_snapshot (
    ticker TEXT NOT NULL,
    exchange TEXT,
    mention_count INTEGER,
    pct_change NUMERIC,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trending_snapshot_count ON trending_tickers_snapshot(mention_count DESC);
