from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def fmt_et(dt: datetime | None) -> str:
    """Renders a timestamptz value (assumed UTC-aware from Postgres) in
    US Eastern time with the correct EST/EDT label. 'Never' if not run yet."""
    if dt is None:
        return "Never"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(EASTERN)
    return local.strftime("%b %d, %Y · %I:%M %p %Z")


def fmt_macro(value: float, units: str | None) -> str:
    """
    Renders a raw macro_observations value as something a human reads at a
    glance, based on its units:
      - Percent / Percentage points -> "4.61%" / "0.45 pts"
      - Index -> "-0.554"
      - Millions/Billions of dollars -> scaled to $M / $B / $T with commas
      - anything else -> comma-grouped raw number, 2 decimals
    """
    if value is None:
        return "—"

    units = units or ""

    if units == "Percent":
        return f"{value:.2f}%"

    if units == "Percentage points":
        return f"{value:+.2f} pts"

    if units == "Index":
        return f"{value:.3f}"

    if units == "Millions of dollars":
        dollars = value * 1_000_000
    elif units == "Billions of dollars":
        dollars = value * 1_000_000_000
    else:
        return f"{value:,.2f}"

    abs_dollars = abs(dollars)
    if abs_dollars >= 1_000_000_000_000:
        return f"${dollars / 1_000_000_000_000:,.2f}T"
    if abs_dollars >= 1_000_000_000:
        return f"${dollars / 1_000_000_000:,.2f}B"
    if abs_dollars >= 1_000_000:
        return f"${dollars / 1_000_000:,.2f}M"
    return f"${dollars:,.0f}"


def fmt_pct(value: float, decimals: int = 1) -> str:
    """Belief/regime probabilities are stored as 0-1 floats; show as a
    plain-language percentage instead of a 15-digit decimal."""
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%"
