from __future__ import annotations

from email.utils import parsedate_to_datetime

import httpx

from app.settings import get_settings

BENZINGA_NEWS_URL = "https://api.benzinga.com/api/v2/news"


class BenzingaError(Exception):
    pass


def _parse_timestamp(value: str | None):
    """Benzinga's created/updated fields are RFC-822 style
    ('Mon, 01 Jan 2024 13:35:14 -0400'), not ISO 8601 — plain
    date.fromisoformat would fail on these."""
    if not value:
        return None
    return parsedate_to_datetime(value)


def _normalize_article(raw: dict) -> dict:
    tickers = [s.get("name") for s in (raw.get("stocks") or []) if s.get("name")]
    channels = [c.get("name") for c in (raw.get("channels") or []) if c.get("name")]
    return {
        "article_id": raw["id"],
        "title": raw.get("title", ""),
        "teaser": raw.get("teaser"),
        "body": raw.get("body"),
        "url": raw.get("url"),
        "author": raw.get("author"),
        "channels": channels,
        "tickers": tickers,
        "published_at": _parse_timestamp(raw.get("created")),
        "updated_at": _parse_timestamp(raw.get("updated")),
    }


def fetch_news(
    tickers: list[str] | None = None,
    updated_since: str | None = None,
    channels: list[str] | None = None,
    page_size: int = 100,
    max_pages: int = 20,
) -> list[dict]:
    """
    Pulls news from Benzinga, paginated, bounded to max_pages so a single
    call always terminates in finite time — important since this runs as
    a job on its own dedicated queue, and an unbounded pull is exactly the
    kind of thing that could hang a worker (same failure mode we already
    hit twice with other jobs).

    tickers=None means no ticker filter at all (the "general market, no
    filter" case) — Benzinga's own default behavior for the endpoint.
    channels=None means no channel filter (pulls every channel); pass a
    list to restrict to specific channels (e.g. ["News", "Markets", "WIIM"]).
    updated_since should be an RFC-822 or ISO date string; pass the
    highest updated_at already stored to only pull deltas, per Benzinga's
    own recommendation for production use.
    """
    settings = get_settings()
    if not settings.benzinga_api_key:
        raise BenzingaError("BENZINGA_API_KEY is not configured")

    headers = {
        "Accept": "application/json",
    }

    all_articles: list[dict] = []

    with httpx.Client(timeout=httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=15.0)) as client:
        for page in range(max_pages):
            params: dict = {
                "token": settings.benzinga_api_key,
                "pageSize": page_size,
                "page": page,
                "displayOutput": "full",
                "sort": "updated",
                "order": "asc",
            }
            if tickers:
                params["tickers"] = ",".join(tickers)
            if updated_since:
                params["updatedSince"] = updated_since
            if channels:
                params["channels"] = ",".join(channels)

            try:
                response = client.get(BENZINGA_NEWS_URL, params=params, headers=headers)
            except httpx.HTTPError as exc:
                raise BenzingaError(f"Request to Benzinga failed: {exc}") from exc

            if response.status_code != 200:
                raise BenzingaError(
                    f"Benzinga API returned {response.status_code}: {response.text[:500]}"
                )

            data = response.json()

            if isinstance(data, dict) and data.get("ok") is False:
                errors = data.get("errors", [])
                raise BenzingaError(f"Benzinga API error: {errors}")

            if not isinstance(data, list) or not data:
                break

            all_articles.extend(_normalize_article(item) for item in data)

            if len(data) < page_size:
                break

    return all_articles
