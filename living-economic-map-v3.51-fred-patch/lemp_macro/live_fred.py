from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import json

import httpx

from app.db import connection
from app.settings import get_settings


@dataclass(frozen=True)
class FredSeriesSpec:
    series_id: str
    title: str
    units: str
    frequency: str
    category: str
    interpretation: str


PRIORITY_SERIES: tuple[FredSeriesSpec, ...] = (
    FredSeriesSpec("WALCL", "Federal Reserve total assets", "Millions of dollars", "Weekly", "Liquidity", "Higher values generally indicate more central-bank liquidity."),
    FredSeriesSpec("RRPONTSYD", "Overnight reverse repurchase agreements", "Billions of dollars", "Daily", "Liquidity", "Falling balances can release liquidity into the financial system."),
    FredSeriesSpec("WTREGEN", "Treasury General Account", "Millions of dollars", "Weekly", "Liquidity", "A rising Treasury cash balance can drain private-sector liquidity."),
    FredSeriesSpec("DFF", "Effective federal funds rate", "Percent", "Daily", "Policy", "Higher rates generally indicate tighter monetary policy."),
    FredSeriesSpec("DGS2", "2-year Treasury yield", "Percent", "Daily", "Rates", "Tracks expected policy and front-end rate pressure."),
    FredSeriesSpec("DGS10", "10-year Treasury yield", "Percent", "Daily", "Rates", "Tracks long-duration discount-rate pressure."),
    FredSeriesSpec("DFII10", "10-year real Treasury yield", "Percent", "Daily", "Rates", "Higher real yields generally pressure long-duration asset valuations."),
    FredSeriesSpec("T10Y2Y", "10-year minus 2-year Treasury spread", "Percentage points", "Daily", "Curve", "A more positive curve can signal easing recession pressure."),
    FredSeriesSpec("NFCI", "Chicago Fed National Financial Conditions Index", "Index", "Weekly", "Financial conditions", "Higher readings indicate tighter financial conditions."),
    FredSeriesSpec("BAMLH0A0HYM2", "ICE BofA US high-yield option-adjusted spread", "Percent", "Daily", "Credit", "Wider spreads indicate greater credit stress."),
)


class FredIngestionError(RuntimeError):
    pass


def _fetch_series(client: httpx.Client, spec: FredSeriesSpec, api_key: str, start: date) -> list[dict[str, Any]]:
    response = client.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": spec.series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start.isoformat(),
            "sort_order": "asc",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if "error_message" in payload:
        raise FredIngestionError(str(payload["error_message"]))
    return payload.get("observations", [])


def ingest_priority_series(*, lookback_days: int = 2200) -> dict[str, Any]:
    settings = get_settings()
    if not settings.fred_api_key:
        raise FredIngestionError("FRED_API_KEY is not configured")

    started = date.today() - timedelta(days=lookback_days)
    errors: list[dict[str, str]] = []
    succeeded = 0
    written = 0

    with connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO macro_ingestion_runs(provider,status,series_requested) VALUES (%s,%s,%s) RETURNING ingestion_run_id",
            ("FRED", "running", len(PRIORITY_SERIES)),
        )
        run_id = cur.fetchone()[0]
        conn.commit()

    with httpx.Client(timeout=30.0, headers={"User-Agent": "LivingEconomicMap/3.51"}) as client:
        for spec in PRIORITY_SERIES:
            try:
                observations = _fetch_series(client, spec, settings.fred_api_key, started)
                with connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        INSERT INTO macro_series(series_id,source,title,units,frequency,category,interpretation,updated_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
                        ON CONFLICT(series_id) DO UPDATE SET
                          title=EXCLUDED.title, units=EXCLUDED.units, frequency=EXCLUDED.frequency,
                          category=EXCLUDED.category, interpretation=EXCLUDED.interpretation, updated_at=NOW()
                        """,
                        (spec.series_id, "FRED", spec.title, spec.units, spec.frequency, spec.category, spec.interpretation),
                    )
                    series_written = 0
                    for item in observations:
                        raw_value = item.get("value")
                        if raw_value in (None, ".", ""):
                            continue
                        cur.execute(
                            """
                            INSERT INTO macro_observations(
                                series_id, observation_date, value, realtime_start, realtime_end, raw_metadata
                            ) VALUES (%s,%s,%s,%s,%s,%s::jsonb)
                            ON CONFLICT(series_id,observation_date,realtime_start) DO UPDATE SET
                                value=EXCLUDED.value,
                                realtime_end=EXCLUDED.realtime_end,
                                retrieved_at=NOW(),
                                raw_metadata=EXCLUDED.raw_metadata
                            """,
                            (
                                spec.series_id,
                                item["date"],
                                float(raw_value),
                                item.get("realtime_start"),
                                item.get("realtime_end"),
                                json.dumps({"source": "FRED", "series_id": spec.series_id}),
                            ),
                        )
                        series_written += 1
                    conn.commit()
                succeeded += 1
                written += series_written
            except Exception as exc:
                errors.append({"series_id": spec.series_id, "error": str(exc)})

    status = "completed" if not errors else ("partial" if succeeded else "failed")
    with connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE macro_ingestion_runs
            SET status=%s, series_succeeded=%s, observations_written=%s,
                error_details=%s::jsonb, completed_at=NOW()
            WHERE ingestion_run_id=%s
            """,
            (status, succeeded, written, json.dumps(errors), run_id),
        )
        conn.commit()

    return {
        "run_id": str(run_id),
        "status": status,
        "series_requested": len(PRIORITY_SERIES),
        "series_succeeded": succeeded,
        "observations_written": written,
        "errors": errors,
    }
