"""
Backtests RatesLiquidityEngine against known historical periods.

Run inside the ingestion/reasoning container (has the Postgres connection
and the full macro_observations history):

    python -m scripts.backtest

Methodology, and why it's trustworthy:
  - Every eval case calls load_signals_asof(cutoff), which filters
    macro_observations to observation_date <= cutoff BEFORE computing any
    change/z-score feature. This is deliberately a separate function from
    the live load_signals() used by the real-time worker, because that one
    always reads the full table regardless of the as_of_date argument —
    reusing it here would leak future data into a "historical" run.
  - Coverage is checked and reported per case, per series, before running.
    If a series' earliest available observation is after the eval date,
    that's reported honestly rather than silently computing on thin data.
  - This prints the engine's actual output next to a short qualitative
    expectation for you to compare — it does NOT auto-grade pass/fail.
    Regime interpretation has real nuance; a human judgment call on
    "did this reasonably call it" is more honest than a fragile automated
    threshold.

Known data-coverage caveat: FRED ingestion's default lookback is 2200
days from TODAY, which as of mid-2026 reaches back to roughly mid-2020 —
NOT far enough for the September 2019 repo-stress case below. That case
will report insufficient coverage unless a deeper backfill has been run
first (see the printed instructions if it does).
"""
from __future__ import annotations

from lemp_rates.adapters import REQUIRED_BARE_SERIES, load_signals_asof, series_coverage
from lemp_rates.engine import RatesLiquidityEngine
from lemp_rates.models import SeriesSignal

EVAL_CASES = [
    {
        "label": "September 2019 repo-market stress",
        "date": "2019-09-17",
        "expect": (
            "SOFR spiked to ~5.25% intraday against a ~2.0-2.25% fed funds "
            "target — expect money_market_stress and/or real_rate_tightening "
            "to read elevated, money_market_liquidity to read low."
        ),
    },
    {
        "label": "COVID-era QE onset",
        "date": "2020-03-23",
        "expect": (
            "The Fed announced open-ended QE and emergency facilities this "
            "week — expect central_bank_liquidity and QE to read elevated, "
            "even amid market panic elsewhere."
        ),
    },
    {
        "label": "2022 tightening cycle (peak hawkishness)",
        "date": "2022-06-13",
        "expect": (
            "Days after a hot CPI print, ahead of the first 75bp hike, with "
            "2yr/10yr yields both spiking — expect real_yield_pressure, "
            "long_rate_pressure, and QT to read elevated; composite_liquidity "
            "to read low."
        ),
    },
]


def check_coverage(cutoff: str) -> list[str]:
    coverage = series_coverage()
    warnings = []
    for bare_id in REQUIRED_BARE_SERIES:
        info = coverage.get(bare_id, {})
        earliest = info.get("earliest")
        if earliest is None:
            warnings.append(f"  {bare_id}: no data at all")
        elif earliest.isoformat() > cutoff:
            warnings.append(
                f"  {bare_id}: earliest available is {earliest.isoformat()}, "
                f"after this eval date — result will be based on partial or no history"
            )
    return warnings


def run_case(case: dict) -> None:
    print("=" * 78)
    print(f"{case['label']}  ({case['date']})")
    print(f"Expected (qualitative): {case['expect']}")
    print("-" * 78)

    warnings = check_coverage(case["date"])
    if warnings:
        print("COVERAGE WARNING — this eval date predates available data for:")
        for w in warnings:
            print(w)
        print(
            "Consider a deeper FRED backfill before trusting this case "
            "(e.g. run ingest_priority_series with lookback_days covering "
            "back to this date) — proceeding anyway with what's available."
        )
        print("-" * 78)

    raw_signals = load_signals_asof(case["date"])
    if not raw_signals:
        print("No signals at all for this date — skipping.")
        print()
        return

    signals = [SeriesSignal(**item) for item in raw_signals]
    engine = RatesLiquidityEngine()
    snapshot = engine.run(signals, case["date"], priors={})

    print(f"Coverage ratio: {snapshot.coverage_ratio:.0%}")
    if snapshot.missing_series:
        print(f"Missing series: {', '.join(snapshot.missing_series)}")

    print(f"\ncomposite_liquidity: {snapshot.composite_liquidity.posterior_probability:.1%}")

    print("\nBeliefs:")
    all_beliefs = dict(snapshot.component_beliefs)
    all_beliefs.update(snapshot.rate_beliefs)
    for key, belief in sorted(all_beliefs.items(), key=lambda kv: kv[1].posterior_probability, reverse=True):
        print(f"  {key}: {belief.posterior_probability:.1%} (confidence {belief.confidence:.0%})")

    print("\nRegimes (sorted by probability):")
    for regime in snapshot.regimes:
        print(f"  {regime.regime_key}: {regime.probability:.1%}")

    print()


def main() -> None:
    print("Backtesting RatesLiquidityEngine against known historical periods.")
    print("Reminder: this is a human-judgment comparison, not an automated pass/fail.\n")
    for case in EVAL_CASES:
        run_case(case)


if __name__ == "__main__":
    main()
