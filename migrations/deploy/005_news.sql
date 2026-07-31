CREATE TABLE IF NOT EXISTS watchlist_tickers (
    ticker TEXT PRIMARY KEY,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS news_articles (
    article_id BIGINT PRIMARY KEY,
    title TEXT NOT NULL,
    teaser TEXT,
    body TEXT,
    url TEXT,
    author TEXT,
    channels JSONB NOT NULL DEFAULT '[]',
    tickers JSONB NOT NULL DEFAULT '[]',
    published_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_published ON news_articles(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_tickers ON news_articles USING GIN (tickers);
