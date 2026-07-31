CREATE TABLE IF NOT EXISTS price_bars (
    ticker TEXT NOT NULL,
    bar_date DATE NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume BIGINT,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ticker, bar_date)
);

CREATE INDEX IF NOT EXISTS idx_price_bars_ticker_date ON price_bars(ticker, bar_date DESC);
