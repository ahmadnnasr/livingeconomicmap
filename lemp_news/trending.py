from __future__ import annotations

import httpx

from app.settings import get_settings

BENZINGA_TRENDING_URL = "https://api.benzinga.com/api/v1/trending-tickers/list"


class BenzingaError(Exception):
    pass


def fetch_trending_tickers(timeframe: str = "1d") -> list[dict]:
    """timeframe: '10m' | '1h' | '1d'. Returns a flat list of
    {ticker, exchange, count, pct_change}, ranked as Benzinga returns
    them (by mention activity)."""
    settings = get_settings()
    if not settings.benzinga_api_key:
        raise BenzingaError("BENZINGA_API_KEY is not configured")

    params = {"token": settings.benzinga_api_key, "timeframe": timeframe}
    headers = {"Accept": "application/json"}

    try:
        response = httpx.get(
            BENZINGA_TRENDING_URL,
            params=params,
            headers=headers,
            timeout=httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=15.0),
        )
    except httpx.HTTPError as exc:
        raise BenzingaError(f"Request to Benzinga trending-tickers failed: {exc}") from exc

    if response.status_code != 200:
        raise BenzingaError(
            f"Benzinga trending-tickers API returned {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    entries = data.get("data", []) if isinstance(data, dict) else []

    result = []
    for entry in entries:
        security = entry.get("security", {})
        result.append(
            {
                "ticker": security.get("ticker"),
                "exchange": security.get("exchange"),
                "count": entry.get("count"),
                "pct_change": entry.get("pct_chg"),
            }
        )
    return result
