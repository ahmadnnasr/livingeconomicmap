from __future__ import annotations

import httpx

from app.settings import get_settings

BENZINGA_EARNINGS_URL = "https://api.benzinga.com/api/v2.1/calendar/earnings"


class BenzingaError(Exception):
    pass


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_earnings(tickers: list[str], date_from: str, date_to: str) -> list[dict]:
    """Watchlist-scoped earnings events (upcoming and/or historical,
    depending on the date range passed in). Empty estimate/actual/surprise
    fields are common and expected — Benzinga populates them progressively
    as an event approaches and then completes."""
    settings = get_settings()
    if not settings.benzinga_api_key:
        raise BenzingaError("BENZINGA_API_KEY is not configured")

    if not tickers:
        return []

    params = {
        "token": settings.benzinga_api_key,
        "parameters[tickers]": ",".join(tickers),
        "parameters[date_from]": date_from,
        "parameters[date_to]": date_to,
        "pagesize": 100,
    }
    headers = {"Accept": "application/json"}

    try:
        response = httpx.get(
            BENZINGA_EARNINGS_URL,
            params=params,
            headers=headers,
            timeout=httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=15.0),
        )
    except httpx.HTTPError as exc:
        raise BenzingaError(f"Request to Benzinga earnings failed: {exc}") from exc

    if response.status_code != 200:
        raise BenzingaError(
            f"Benzinga earnings API returned {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    raw_events = data.get("earnings", []) if isinstance(data, dict) else []

    result = []
    for e in raw_events:
        result.append(
            {
                "benzinga_id": e.get("id"),
                "ticker": e.get("ticker"),
                "company_name": e.get("name"),
                "event_date": e.get("date"),
                "date_confirmed": bool(int(e["date_confirmed"])) if e.get("date_confirmed") not in (None, "") else None,
                "period": e.get("period"),
                "period_year": e.get("period_year"),
                "eps_estimate": _to_float(e.get("eps_est")),
                "eps_actual": _to_float(e.get("eps")),
                "eps_surprise_percent": _to_float(e.get("eps_surprise_percent")),
                "revenue_estimate": _to_float(e.get("revenue_est")),
                "revenue_actual": _to_float(e.get("revenue")),
                "revenue_surprise_percent": _to_float(e.get("revenue_surprise_percent")),
                "importance": e.get("importance"),
            }
        )
    return result
