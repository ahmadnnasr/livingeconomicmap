CREATE TABLE IF NOT EXISTS earnings_calendar (
    benzinga_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    company_name TEXT,
    event_date DATE,
    date_confirmed BOOLEAN,
    period TEXT,
    period_year INTEGER,
    eps_estimate NUMERIC,
    eps_actual NUMERIC,
    eps_surprise_percent NUMERIC,
    revenue_estimate NUMERIC,
    revenue_actual NUMERIC,
    revenue_surprise_percent NUMERIC,
    importance INTEGER,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_earnings_ticker_date ON earnings_calendar(ticker, event_date DESC);
