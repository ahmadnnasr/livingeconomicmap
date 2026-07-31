from __future__ import annotations

from datetime import datetime

import httpx

from app.settings import get_settings

BENZINGA_BARS_URL = "https://api.benzinga.com/api/v2/bars"


class BenzingaError(Exception):
    pass


def _parse_bar_datetime(value: str):
    """Bars 'dateTime' field is ISO 8601 with a numeric UTC offset
    (e.g. '2025-12-08T09:00:00.000-05:00') — plain fromisoformat handles
    this fine in Python 3.11+, but we go through datetime.fromisoformat
    explicitly since bars' format differs from news' RFC-822 style."""
    return datetime.fromisoformat(value)


def fetch_daily_bars(tickers: list[str], from_date: str, to_date: str) -> dict[str, list[dict]]:
    """
    Pulls daily OHLCV bars for the given tickers between from_date and
    to_date (both 'YYYY-MM-DD'). Returns {ticker: [bar, ...]}. Benzinga's
    bars endpoint takes multiple symbols per call, so this is one request
    per call rather than paginating — a 3-year daily backfill for a
    reasonable watchlist size is well within a single response.
    """
    settings = get_settings()
    if not settings.benzinga_api_key:
        raise BenzingaError("BENZINGA_API_KEY is not configured")

    if not tickers:
        return {}

    params = {
        "token": settings.benzinga_api_key,
        "symbols": ",".join(tickers),
        "interval": "1D",
        "from": from_date,
        "to": to_date,
    }
    headers = {"Accept": "application/json"}

    try:
        response = httpx.get(
            BENZINGA_BARS_URL,
            params=params,
            headers=headers,
            timeout=httpx.Timeout(connect=15.0, read=60.0, write=15.0, pool=15.0),
        )
    except httpx.HTTPError as exc:
        raise BenzingaError(f"Request to Benzinga bars failed: {exc}") from exc

    if response.status_code != 200:
        raise BenzingaError(
            f"Benzinga bars API returned {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    if not isinstance(data, list):
        raise BenzingaError(f"Unexpected bars response shape: {str(data)[:300]}")

    result: dict[str, list[dict]] = {}
    for entry in data:
        symbol = entry.get("symbol")
        candles = entry.get("candles", [])
        bars = []
        for c in candles:
            dt = _parse_bar_datetime(c["dateTime"])
            bars.append(
                {
                    "bar_date": dt.date(),
                    "open": c.get("open"),
                    "high": c.get("high"),
                    "low": c.get("low"),
                    "close": c.get("close"),
                    "volume": int(c["volume"]) if c.get("volume") not in (None, "") else None,
                }
            )
        if symbol:
            result[symbol] = bars

    return result
