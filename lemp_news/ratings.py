from __future__ import annotations

import httpx

from app.settings import get_settings

BENZINGA_RATINGS_URL = "https://api.benzinga.com/api/v2/calendar/ratings"


class BenzingaError(Exception):
    pass


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_recent_ratings(
    date_from: str,
    date_to: str,
    min_importance: int = 3,
    page_size: int = 100,
) -> list[dict]:
    """
    Market-wide discovery of meaningful analyst rating actions in a date
    window — no ticker filter, since the goal is surfacing names you
    don't already track, not looking up a specific stock. min_importance
    uses Benzinga's own 0-5 subjective importance scale to filter out
    routine/low-signal actions.
    """
    settings = get_settings()
    if not settings.benzinga_api_key:
        raise BenzingaError("BENZINGA_API_KEY is not configured")

    params = {
        "token": settings.benzinga_api_key,
        "parameters[date_from]": date_from,
        "parameters[date_to]": date_to,
        "parameters[importance]": min_importance,
        "pagesize": page_size,
    }
    headers = {"Accept": "application/json"}

    try:
        response = httpx.get(
            BENZINGA_RATINGS_URL,
            params=params,
            headers=headers,
            timeout=httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=15.0),
        )
    except httpx.HTTPError as exc:
        raise BenzingaError(f"Request to Benzinga ratings failed: {exc}") from exc

    if response.status_code != 200:
        raise BenzingaError(
            f"Benzinga ratings API returned {response.status_code}: {response.text[:500]}"
        )

    data = response.json()
    raw_ratings = data.get("ratings", []) if isinstance(data, dict) else []

    result = []
    for r in raw_ratings:
        result.append(
            {
                "benzinga_id": r.get("id"),
                "ticker": r.get("ticker"),
                "company_name": r.get("name"),
                "rating_date": r.get("date"),
                "action_company": r.get("action_company"),
                "action_pt": r.get("action_pt"),
                "rating_current": r.get("rating_current"),
                "rating_prior": r.get("rating_prior"),
                "pt_current": _to_float(r.get("adjusted_pt_current") or r.get("pt_current")),
                "pt_prior": _to_float(r.get("adjusted_pt_prior") or r.get("pt_prior")),
                "analyst_name": r.get("analyst_name"),
                "analyst_firm": r.get("analyst"),
                "importance": r.get("importance"),
            }
        )
    return result
