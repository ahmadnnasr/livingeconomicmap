from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import httpx

from app.db import connection
from app.settings import get_settings


FRED_OBSERVATIONS_URL = (
    "https://api.stlouisfed.org/fred/series/observations"
)


@dataclass(frozen=True)
class FredSeriesSpec:
    series_id: str
    title: str
    units: str
    frequency: str
    category: str
    interpretation: str


PRIORITY_SERIES: tuple[FredSeriesSpec, ...] = (
    FredSeriesSpec(
        "WALCL",
        "Federal Reserve total assets",
        "Millions of dollars",
        "Weekly",
        "Liquidity",
        "Higher values generally indicate more central-bank liquidity.",
    ),
    FredSeriesSpec(
        "WRESBAL",
        "Reserve balances with Federal Reserve Banks",
        "Millions of dollars",
        "Weekly",
        "Liquidity",
        "Higher reserve balances generally indicate more central-bank liquidity.",
    ),
    FredSeriesSpec(
        "SOFR",
        "Secured overnight financing rate",
        "Percent",
        "Daily",
        "Policy",
        "Elevated SOFR relative to policy rate can indicate money-market funding stress.",
    ),
    FredSeriesSpec(
        "RRPONTSYD",
        "Overnight reverse repurchase agreements",
        "Billions of dollars",
        "Daily",
        "Liquidity",
        "Falling balances can release liquidity into the financial system.",
    ),
    FredSeriesSpec(
        "WTREGEN",
        "Treasury General Account",
        "Millions of dollars",
        "Weekly",
        "Liquidity",
        "A rising Treasury cash balance can drain private-sector liquidity.",
    ),
    FredSeriesSpec(
        "DFF",
        "Effective federal funds rate",
        "Percent",
        "Daily",
        "Policy",
        "Higher rates generally indicate tighter monetary policy.",
    ),
    FredSeriesSpec(
        "DGS2",
        "2-year Treasury yield",
        "Percent",
        "Daily",
        "Rates",
        "Tracks expected policy and front-end rate pressure.",
    ),
    FredSeriesSpec(
        "DGS10",
        "10-year Treasury yield",
        "Percent",
        "Daily",
        "Rates",
        "Tracks long-duration discount-rate pressure.",
    ),
    FredSeriesSpec(
        "DFII10",
        "10-year real Treasury yield",
        "Percent",
        "Daily",
        "Rates",
        "Higher real yields generally pressure long-duration asset valuations.",
    ),
    FredSeriesSpec(
        "T10Y2Y",
        "10-year minus 2-year Treasury spread",
        "Percentage points",
        "Daily",
        "Curve",
        "A more positive curve can signal easing recession pressure.",
    ),
    FredSeriesSpec(
        "NFCI",
        "Chicago Fed National Financial Conditions Index",
        "Index",
        "Weekly",
        "Financial conditions",
        "Higher readings indicate tighter financial conditions.",
    ),
    FredSeriesSpec(
        "BAMLH0A0HYM2",
        "ICE BofA US high-yield option-adjusted spread",
        "Percent",
        "Daily",
        "Credit",
        "Wider spreads indicate greater credit stress.",
    ),
)


class FredIngestionError(RuntimeError):
    pass


def _fetch_series(
    client: httpx.Client,
    spec: FredSeriesSpec,
    api_key: str,
    start: date,
    *,
    max_attempts: int = 3,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            print(
                f"fred_fetch_started "
                f"series={spec.series_id} "
                f"attempt={attempt}/{max_attempts}",
                flush=True,
            )

            response = client.get(
                FRED_OBSERVATIONS_URL,
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
                raise FredIngestionError(
                    str(payload["error_message"])
                )

            observations = payload.get("observations", [])

            print(
                f"fred_fetch_completed "
                f"series={spec.series_id} "
                f"observations={len(observations)}",
                flush=True,
            )

            return observations

        except (
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.ConnectError,
            httpx.RemoteProtocolError,
        ) as exc:
            last_error = exc

            print(
                f"fred_fetch_retry "
                f"series={spec.series_id} "
                f"attempt={attempt}/{max_attempts} "
                f"error={type(exc).__name__}: {exc}",
                flush=True,
            )

            if attempt < max_attempts:
                delay_seconds = (
                    2 ** (attempt - 1)
                    + random.uniform(0.0, 0.75)
                )
                time.sleep(delay_seconds)

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code

            # Retry temporary upstream failures and rate limits.
            if status_code == 429 or status_code >= 500:
                last_error = exc

                print(
                    f"fred_http_retry "
                    f"series={spec.series_id} "
                    f"status={status_code} "
                    f"attempt={attempt}/{max_attempts}",
                    flush=True,
                )

                if attempt < max_attempts:
                    delay_seconds = (
                        2 ** (attempt - 1)
                        + random.uniform(0.0, 0.75)
                    )
                    time.sleep(delay_seconds)

                continue

            raise FredIngestionError(
                f"FRED returned HTTP {status_code} "
                f"for series {spec.series_id}: "
                f"{exc.response.text[:500]}"
            ) from exc

        except ValueError as exc:
            raise FredIngestionError(
                f"FRED returned invalid JSON for "
                f"series {spec.series_id}"
            ) from exc

    raise FredIngestionError(
        f"FRED request failed for {spec.series_id} "
        f"after {max_attempts} attempts: {last_error}"
    )


def _write_series(
    spec: FredSeriesSpec,
    observations: list[dict[str, Any]],
) -> int:
    with connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO macro_series (
                series_id,
                source,
                title,
                units,
                frequency,
                category,
                interpretation,
                updated_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                NOW()
            )
            ON CONFLICT (series_id)
            DO UPDATE SET
                title = EXCLUDED.title,
                units = EXCLUDED.units,
                frequency = EXCLUDED.frequency,
                category = EXCLUDED.category,
                interpretation = EXCLUDED.interpretation,
                updated_at = NOW()
            """,
            (
                spec.series_id,
                "FRED",
                spec.title,
                spec.units,
                spec.frequency,
                spec.category,
                spec.interpretation,
            ),
        )

        series_written = 0

        for item in observations:
            raw_value = item.get("value")

            if raw_value in (None, ".", ""):
                continue

            cur.execute(
                """
                INSERT INTO macro_observations (
                    series_id,
                    observation_date,
                    value,
                    realtime_start,
                    realtime_end,
                    raw_metadata
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s::jsonb
                )
                ON CONFLICT (
                    series_id,
                    observation_date,
                    realtime_start
                )
                DO UPDATE SET
                    value = EXCLUDED.value,
                    realtime_end = EXCLUDED.realtime_end,
                    retrieved_at = NOW(),
                    raw_metadata = EXCLUDED.raw_metadata
                """,
                (
                    spec.series_id,
                    item["date"],
                    float(raw_value),
                    item.get("realtime_start"),
                    item.get("realtime_end"),
                    json.dumps(
                        {
                            "source": "FRED",
                            "series_id": spec.series_id,
                        }
                    ),
                ),
            )

            series_written += 1

        conn.commit()

    return series_written


def ingest_priority_series(
    *,
    lookback_days: int = 30,
) -> dict[str, Any]:
    settings = get_settings()

    if not settings.fred_api_key:
        raise FredIngestionError(
            "FRED_API_KEY is not configured"
        )

    observation_start = (
        date.today()
        - timedelta(days=lookback_days)
    )

    errors: list[dict[str, str]] = []
    succeeded = 0
    written = 0

    with connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO macro_ingestion_runs (
                provider,
                status,
                series_requested
            )
            VALUES (%s, %s, %s)
            RETURNING ingestion_run_id
            """,
            (
                "FRED",
                "running",
                len(PRIORITY_SERIES),
            ),
        )

        run_id = cur.fetchone()[0]
        conn.commit()

    timeout = httpx.Timeout(
        connect=15.0,
        read=60.0,
        write=30.0,
        pool=15.0,
    )

    limits = httpx.Limits(
        max_connections=5,
        max_keepalive_connections=2,
        keepalive_expiry=20.0,
    )

    with httpx.Client(
        timeout=timeout,
        limits=limits,
        headers={
            "Accept": "application/json",
        },
        follow_redirects=True,
        http2=False,
    ) as client:
        for spec in PRIORITY_SERIES:
            try:
                observations = _fetch_series(
                    client,
                    spec,
                    settings.fred_api_key,
                    observation_start,
                )

                series_written = _write_series(
                    spec,
                    observations,
                )

                succeeded += 1
                written += series_written

                print(
                    f"fred_series_stored "
                    f"series={spec.series_id} "
                    f"rows={series_written}",
                    flush=True,
                )

            except Exception as exc:
                error_message = (
                    f"{type(exc).__name__}: {exc}"
                )

                errors.append(
                    {
                        "series_id": spec.series_id,
                        "error": error_message,
                    }
                )

                print(
                    f"fred_series_failed "
                    f"series={spec.series_id} "
                    f"error={error_message}",
                    flush=True,
                )

    if not errors:
        status = "completed"
    elif succeeded:
        status = "partial"
    else:
        status = "failed"

    with connection() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE macro_ingestion_runs
            SET
                status = %s,
                series_succeeded = %s,
                observations_written = %s,
                error_details = %s::jsonb,
                completed_at = NOW()
            WHERE ingestion_run_id = %s
            """,
            (
                status,
                succeeded,
                written,
                json.dumps(errors),
                run_id,
            ),
        )

        conn.commit()

    result = {
        "run_id": str(run_id),
        "status": status,
        "series_requested": len(PRIORITY_SERIES),
        "series_succeeded": succeeded,
        "observations_written": written,
        "errors": errors,
    }

    # Make the queue retry when nothing was retrieved.
    if succeeded == 0:
        raise FredIngestionError(
            "All FRED series failed. "
            f"Run ID: {run_id}. Errors: {errors}"
        )

    return result
