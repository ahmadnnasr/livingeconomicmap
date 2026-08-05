from __future__ import annotations

import json

from app.db import connection, execute, fetch_all

DEFAULT_RETENTION_DAYS = 21


def _safe_fetch(query, params=()):
    try:
        return fetch_all(query, params)
    except Exception:
        return []


def persist_trending_snapshot(entries: list[dict]) -> int:
    """Overwrites the whole snapshot each run — this is a point-in-time
    discovery feed, not something that needs historical accumulation
    the way news/bars do."""
    with connection() as conn:
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE trending_tickers_snapshot")
        for e in entries:
            cur.execute(
                """
                INSERT INTO trending_tickers_snapshot (ticker, exchange, mention_count, pct_change)
                VALUES (%s, %s, %s, %s)
                """,
                (e.get("ticker"), e.get("exchange"), e.get("count"), e.get("pct_change")),
            )
        conn.commit()
    return len(entries)


def latest_trending_snapshot(limit: int = 25) -> list[dict]:
    return _safe_fetch(
        "SELECT ticker, exchange, mention_count, pct_change, snapshot_at FROM trending_tickers_snapshot ORDER BY mention_count DESC LIMIT %s",
        (limit,),
    )


def persist_ratings_snapshot(entries: list[dict]) -> int:
    with connection() as conn:
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE ratings_snapshot")
        for e in entries:
            cur.execute(
                """
                INSERT INTO ratings_snapshot (
                    benzinga_id, ticker, company_name, rating_date, action_company,
                    action_pt, rating_current, rating_prior, pt_current, pt_prior,
                    analyst_name, analyst_firm, importance
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    e.get("benzinga_id"), e.get("ticker"), e.get("company_name"),
                    e.get("rating_date"), e.get("action_company"), e.get("action_pt"),
                    e.get("rating_current"), e.get("rating_prior"),
                    e.get("pt_current"), e.get("pt_prior"),
                    e.get("analyst_name"), e.get("analyst_firm"), e.get("importance"),
                ),
            )
        conn.commit()
    return len(entries)


def latest_ratings_snapshot(limit: int = 30) -> list[dict]:
    return _safe_fetch(
        "SELECT * FROM ratings_snapshot ORDER BY rating_date DESC, importance DESC LIMIT %s",
        (limit,),
    )


def persist_earnings(entries: list[dict]) -> int:
    written = 0
    with connection() as conn:
        cur = conn.cursor()
        for e in entries:
            if not e.get("benzinga_id"):
                continue
            cur.execute(
                """
                INSERT INTO earnings_calendar (
                    benzinga_id, ticker, company_name, event_date, date_confirmed,
                    period, period_year, eps_estimate, eps_actual, eps_surprise_percent,
                    revenue_estimate, revenue_actual, revenue_surprise_percent, importance
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (benzinga_id) DO UPDATE SET
                    eps_actual = EXCLUDED.eps_actual,
                    eps_surprise_percent = EXCLUDED.eps_surprise_percent,
                    revenue_actual = EXCLUDED.revenue_actual,
                    revenue_surprise_percent = EXCLUDED.revenue_surprise_percent,
                    date_confirmed = EXCLUDED.date_confirmed,
                    fetched_at = NOW()
                """,
                (
                    e["benzinga_id"], e.get("ticker"), e.get("company_name"),
                    e.get("event_date"), e.get("date_confirmed"),
                    e.get("period"), e.get("period_year"),
                    e.get("eps_estimate"), e.get("eps_actual"), e.get("eps_surprise_percent"),
                    e.get("revenue_estimate"), e.get("revenue_actual"), e.get("revenue_surprise_percent"),
                    e.get("importance"),
                ),
            )
            written += 1
        conn.commit()
    return written


def upcoming_earnings(limit: int = 20) -> list[dict]:
    return _safe_fetch(
        "SELECT * FROM earnings_calendar WHERE event_date >= CURRENT_DATE ORDER BY event_date ASC LIMIT %s",
        (limit,),
    )


def historical_earnings(limit: int = 20) -> list[dict]:
    return _safe_fetch(
        "SELECT * FROM earnings_calendar WHERE event_date < CURRENT_DATE AND eps_actual IS NOT NULL ORDER BY event_date DESC LIMIT %s",
        (limit,),
    )


def load_watchlist() -> list[str]:
    rows = _safe_fetch("SELECT ticker FROM watchlist_tickers ORDER BY ticker")
    return [row["ticker"] for row in rows]


def add_ticker(ticker: str) -> None:
    ticker = ticker.strip().upper()
    if not ticker:
        return
    execute(
        "INSERT INTO watchlist_tickers (ticker) VALUES (%s) ON CONFLICT (ticker) DO NOTHING",
        (ticker,),
    )


def remove_ticker(ticker: str) -> None:
    execute(
        "DELETE FROM watchlist_tickers WHERE ticker = %s",
        (ticker.strip().upper(),),
    )


def persist_articles(articles: list[dict]) -> int:
    """
    Upserts by article_id (Benzinga's own numeric id) — safe to call
    repeatedly with overlapping pulls; a corrected/updated article just
    overwrites the stored copy rather than duplicating.
    """
    written = 0
    with connection() as conn:
        cur = conn.cursor()
        for article in articles:
            cur.execute(
                """
                INSERT INTO news_articles (
                    article_id, title, teaser, body, url, author,
                    channels, tickers, published_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
                ON CONFLICT (article_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    teaser = EXCLUDED.teaser,
                    body = EXCLUDED.body,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    article["article_id"],
                    article["title"],
                    article.get("teaser"),
                    article.get("body"),
                    article.get("url"),
                    article.get("author"),
                    json.dumps(article.get("channels", [])),
                    json.dumps(article.get("tickers", [])),
                    article.get("published_at"),
                    article.get("updated_at"),
                ),
            )
            written += 1
        conn.commit()
    return written


def latest_updated_at() -> str | None:
    """Watermark for incremental Benzinga pulls (updatedSince) — the
    highest updated_at we've already stored, so a repeat pull only asks
    for deltas rather than re-requesting everything. Benzinga's backend
    parses this as a Unix timestamp integer (confirmed from a real 400
    error: 'strconv.ParseInt: parsing ISO-string: invalid syntax') — NOT
    an ISO 8601 string, despite that being a more common convention."""
    rows = _safe_fetch("SELECT MAX(updated_at) AS ts FROM news_articles")
    ts = rows[0]["ts"] if rows else None
    return str(int(ts.timestamp())) if ts else None


def cleanup_old_articles(retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    with connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM news_articles WHERE published_at < NOW() - (%s || ' days')::interval",
            (retention_days,),
        )
        deleted = cur.rowcount
        conn.commit()
    return deleted


def _normalize_rows(rows: list[dict]) -> list[dict]:
    """Defensively ensures 'tickers' is a real Python list on every row —
    the template's |join filter needs this, and while psycopg3 normally
    auto-parses jsonb, this hedges the same way latest_narrative() and
    latest_asset_analysis() already do rather than assuming."""
    for row in rows:
        if "tickers" in row and isinstance(row["tickers"], str):
            row["tickers"] = json.loads(row["tickers"])
    return rows


def recent_wiim_articles(limit: int = 30) -> list[dict]:
    """Why Is It Moving items are just regular news articles tagged with
    a 'WIIM' channel — no separate ingestion needed, just a filter on
    data already pulled by news_ingestion."""
    return _normalize_rows(_safe_fetch(
        """
        SELECT article_id, title, teaser, url, author, tickers, published_at
        FROM news_articles
        WHERE channels ? 'WIIM'
        ORDER BY published_at DESC
        LIMIT %s
        """,
        (limit,),
    ))


def recent_articles_for_watchlist(limit: int = 50) -> list[dict]:
    watchlist = load_watchlist()
    if not watchlist:
        return []
    return _normalize_rows(_safe_fetch(
        """
        SELECT article_id, title, teaser, url, author, tickers, published_at
        FROM news_articles
        WHERE tickers ?| %s
        ORDER BY published_at DESC
        LIMIT %s
        """,
        (watchlist, limit),
    ))


def recent_articles_market(limit: int = 50) -> list[dict]:
    return _normalize_rows(_safe_fetch(
        """
        SELECT article_id, title, teaser, url, author, tickers, published_at
        FROM news_articles
        ORDER BY published_at DESC
        LIMIT %s
        """,
        (limit,),
    ))


def articles_for_digest(hours: int = 24) -> list[dict]:
    """Watchlist-scoped articles from the last N hours — the input to the
    holdings digest."""
    watchlist = load_watchlist()
    if not watchlist:
        return []
    return _normalize_rows(_safe_fetch(
        """
        SELECT title, teaser, tickers, published_at
        FROM news_articles
        WHERE tickers ?| %s
          AND published_at > NOW() - (%s || ' hours')::interval
        ORDER BY published_at DESC
        """,
        (watchlist, hours),
    ))


def persist_news_digest(as_of_date: str, digest_text: str, ticker_count: int, article_count: int) -> str:
    with connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO publications (publication_type, subject, payload, status, model_version)
            VALUES (%s, %s, %s::jsonb, %s, %s)
            RETURNING publication_id
            """,
            (
                "news_digest",
                f"Holdings news digest — {as_of_date}",
                json.dumps(
                    {
                        "as_of_date": as_of_date,
                        "digest": digest_text,
                        "ticker_count": ticker_count,
                        "article_count": article_count,
                    }
                ),
                "rendered",
                "news_digest_v1",
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return str(row[0]) if row else ""
