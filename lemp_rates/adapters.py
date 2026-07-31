from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from datetime import date

from app.db import execute, fetch_all
from .spec import SERIES_SPECS

MODEL_VERSION = "rates_liquidity_v1"

# SERIES_SPECS keys are "fred:XXXX"; macro_observations stores the bare
# series_id ("XXXX"). This is the only place that mapping is stripped/added.
REQUIRED_BARE_SERIES = [key.split(":", 1)[1] for key in SERIES_SPECS]


@dataclass
class SimpleJob:
    """Minimal stand-in for the richer lemp_queue Job object — just enough
    attribute surface for RatesLiquidityReasoningHandler.__call__."""

    payload: dict
    trace_id: str | None = None


def _series_history(bare_series_id: str) -> list[dict]:
    return fetch_all(
        """
        SELECT DISTINCT ON (observation_date)
            observation_date, value
        FROM macro_observations
        WHERE series_id = %s
        ORDER BY observation_date, retrieved_at DESC
        """,
        (bare_series_id,),
    )


def _compute_feature(feature: str, values: list[float]) -> float | None:
    if feature == "level":
        return values[-1] if values else None

    if feature == "change_4":
        if len(values) < 5:
            return None
        return values[-1] - values[-5]

    if feature == "z_score":
        window = values[-252:] if len(values) > 252 else values
        if len(window) < 10:
            return None
        mean = statistics.mean(window)
        stdev = statistics.pstdev(window)
        if stdev == 0:
            return None
        return (values[-1] - mean) / stdev

    return None


def _series_history_asof(bare_series_id: str, cutoff_date: str) -> list[dict]:
    """Same as _series_history but bounded to observation_date <= cutoff —
    required for backtesting so a historical run only ever sees data that
    would genuinely have existed on that date, not the full table up to
    today."""
    return fetch_all(
        """
        SELECT DISTINCT ON (observation_date)
            observation_date, value
        FROM macro_observations
        WHERE series_id = %s AND observation_date <= %s
        ORDER BY observation_date, retrieved_at DESC
        """,
        (bare_series_id, cutoff_date),
    )


def load_signals_asof(cutoff_date: str) -> list[dict]:
    """
    Backtesting variant of load_signals(): every feature (level, change_4,
    z_score) is computed only from observations on or before cutoff_date.
    load_signals() itself is NOT safe for this — it always pulls the full
    history regardless of the as_of_date argument, so a naive "run it for
    a past date" would silently leak future data into the z-scores and
    changes. This function is the one that actually respects the cutoff.
    """
    signals: list[dict] = []
    as_of = date.fromisoformat(cutoff_date)

    for bare_id in REQUIRED_BARE_SERIES:
        rows = _series_history_asof(bare_id, cutoff_date)
        if not rows:
            continue

        values = [row["value"] for row in rows]
        latest_date = rows[-1]["observation_date"]
        freshness_days = (as_of - latest_date).days

        spec = SERIES_SPECS[f"fred:{bare_id}"]
        feature_value = _compute_feature(spec["feature"], values)

        signal = {
            "series_id": f"fred:{bare_id}",
            "as_of_date": cutoff_date,
            "level": values[-1],
            "freshness_days": max(0, freshness_days),
            "source_reliability": 1.0,
        }
        signal[spec["feature"]] = feature_value
        signals.append(signal)

    return signals


def series_coverage() -> dict[str, dict]:
    """Earliest/latest observation_date actually available per required
    series — used by the backtest script to warn honestly when a
    requested eval date predates the data on hand, rather than silently
    running on partial coverage."""
    coverage = {}
    for bare_id in REQUIRED_BARE_SERIES:
        rows = fetch_all(
            "SELECT MIN(observation_date) AS earliest, MAX(observation_date) AS latest "
            "FROM macro_observations WHERE series_id = %s",
            (bare_id,),
        )
        coverage[bare_id] = rows[0] if rows else {"earliest": None, "latest": None}
    return coverage


def load_signals(as_of_date: str) -> list[dict]:
    """
    Build one signal dict per required series, matching the SeriesSignal
    dataclass fields. Feature values (level/change_4/z_score) are derived
    from macro_observations history — nothing here invents data; a series
    with too little history simply yields feature=None and gets skipped
    by the scorer (coverage_ratio reflects that honestly).
    """
    as_of = date.fromisoformat(as_of_date)
    signals: list[dict] = []

    for bare_id in REQUIRED_BARE_SERIES:
        rows = _series_history(bare_id)
        if not rows:
            continue

        values = [row["value"] for row in rows]
        latest_date = rows[-1]["observation_date"]
        freshness_days = (as_of - latest_date).days

        spec = SERIES_SPECS[f"fred:{bare_id}"]
        feature_value = _compute_feature(spec["feature"], values)

        signal = {
            "series_id": f"fred:{bare_id}",
            "as_of_date": as_of_date,
            "level": values[-1],
            "freshness_days": max(0, freshness_days),
            "source_reliability": 1.0,
        }
        signal[spec["feature"]] = feature_value
        signals.append(signal)

    return signals


def load_priors(as_of_date: str) -> dict[str, float]:
    """Most recent posterior probability per belief_key becomes the next
    run's prior. Empty dict (all beliefs default to 0.50) on a first run."""
    rows = fetch_all(
        """
        SELECT DISTINCT ON (belief_key) belief_key, probability
        FROM beliefs
        ORDER BY belief_key, updated_at DESC
        """
    )
    return {row["belief_key"]: row["probability"] for row in rows}


def persist_snapshot(snapshot) -> str:
    """
    Writes every belief (components + rates + composite) and every regime
    from this snapshot as new rows — beliefs/regimes are append-only history
    tables (no upsert), matching how the dashboard already queries them
    with ORDER BY updated_at DESC LIMIT N.
    """
    all_beliefs = list(snapshot.component_beliefs.values())
    all_beliefs.extend(snapshot.rate_beliefs.values())
    all_beliefs.append(snapshot.composite_liquidity)

    for belief in all_beliefs:
        execute(
            """
            INSERT INTO beliefs (belief_key, probability, confidence, evidence, model_version)
            VALUES (%s, %s, %s, %s::jsonb, %s)
            """,
            (
                belief.belief_key,
                belief.posterior_probability,
                belief.confidence,
                json.dumps([asdict(item) for item in belief.evidence]),
                MODEL_VERSION,
            ),
        )

    for regime in snapshot.regimes:
        execute(
            """
            INSERT INTO regimes (regime_key, probability, evidence, model_version)
            VALUES (%s, %s, %s::jsonb, %s)
            """,
            (
                regime.regime_key,
                regime.probability,
                json.dumps(regime.supporting_beliefs),
                MODEL_VERSION,
            ),
        )

    return f"{snapshot.as_of_date}:{MODEL_VERSION}"
