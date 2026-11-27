"""Pure calculation functions for solar battery ETA."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from collections.abc import Sequence


@dataclass(frozen=True)
class Forecast:
    """A battery or aggregate forecast."""

    status: str
    eta: datetime | None = None


def valid_soc(value: object) -> float | None:
    """Accept only finite percentages."""
    try:
        soc = float(str(value))
    except (ValueError, TypeError):
        return None
    return soc if isfinite(soc) and 0 <= soc <= 100 else None


def slope(points: Sequence[tuple[float, float]]) -> float | None:
    """Return least-squares slope in percentage points per minute."""
    if len(points) < 2:
        return None
    mx = sum(x for x, _ in points) / len(points)
    my = sum(y for _, y in points) / len(points)
    denominator = sum((x - mx) ** 2 for x, _ in points)
    if not denominator:
        return None
    return sum((x - mx) * (y - my) for x, y in points) / denominator


def forecast(
    *, now: datetime, soc: float | None, rate: float | None,
    sunset: datetime | None, daylight: bool,
    threshold: float = 99.5, full_since: datetime | None = None,
) -> Forecast:
    """Calculate today's solar-only ETA; fail closed without daylight data."""
    if valid_soc(soc) is None:
        return Forecast("unavailable")
    assert soc is not None
    if soc >= threshold:
        return Forecast("full", full_since or now)
    if not daylight:
        return Forecast("not_charging")
    if sunset is None or sunset <= now:
        return Forecast("unavailable")
    if rate is None:
        return Forecast("insufficient_data")
    if not isfinite(rate) or rate < 0.01:
        return Forecast("not_charging")
    minutes = (threshold - soc) / rate
    if minutes > (sunset - now).total_seconds() / 60:
        return Forecast("charging_past_sunset")
    return Forecast("charging", now + timedelta(minutes=minutes))


def aggregate(items: Sequence[Forecast]) -> Forecast:
    """Predict when every configured battery will be full."""
    if not items or any(x.status == "unavailable" for x in items):
        return Forecast("unavailable")
    if all(x.status == "full" for x in items):
        times = [x.eta for x in items if x.eta is not None]
        return Forecast("full", max(times) if times else None)
    pending = [x for x in items if x.status != "full"]
    for status in ("charging_past_sunset", "not_charging", "insufficient_data"):
        if any(x.status == status for x in pending):
            return Forecast(status)
    if any(x.status != "charging" or x.eta is None for x in pending):
        return Forecast("insufficient_data")
    return Forecast("charging", max(x.eta for x in pending if x.eta is not None))
