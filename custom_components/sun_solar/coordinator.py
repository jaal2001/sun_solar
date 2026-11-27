"""Sample battery SOC and calculate a solar-only forecast."""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .calculation import forecast, slope, valid_soc
from .const import (
    CONF_BATTERY_SOC_ENTITY, DOMAIN, SOC_FULL_THRESHOLD,
    SOC_RATE_WINDOW_MINUTES, SUN_ENTITY_ID, UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SunSolarData:
    eta: datetime | None
    status: str
    soc_rate_percent_per_hour: float | None
    samples_in_window: int


class SunSolarCoordinator(DataUpdateCoordinator[SunSolarData]):
    """Maintain an independent rolling SOC history for each entry."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS))
        self._entry = entry
        self._soc_samples: deque[tuple[datetime, float]] = deque()
        self._full_since: datetime | None = None

    async def _async_update_data(self) -> SunSolarData:
        now = dt_util.utcnow()
        entity_id = self._entry.options.get(
            CONF_BATTERY_SOC_ENTITY, self._entry.data[CONF_BATTERY_SOC_ENTITY]
        )
        state = self.hass.states.get(entity_id)
        soc = valid_soc(state.state) if state else None
        threshold = float(self._entry.options.get("full_threshold", SOC_FULL_THRESHOLD))
        window = int(self._entry.options.get("window_minutes", SOC_RATE_WINDOW_MINUTES))
        sun = self.hass.states.get(SUN_ENTITY_ID)
        daylight = sun is not None and sun.state == "above_horizon"
        raw = sun.attributes.get("next_setting") if sun else None
        sunset = dt_util.parse_datetime(raw) if isinstance(raw, str) else raw
        if not isinstance(sunset, datetime) or sunset.tzinfo is None:
            sunset = None

        if soc is None or not daylight:
            self._soc_samples.clear()
        elif self._soc_samples and now - self._soc_samples[-1][0] > timedelta(
            seconds=UPDATE_INTERVAL_SECONDS * 3
        ):
            self._soc_samples.clear()

        if soc is not None and daylight:
            self._soc_samples.append((now, soc))
        cutoff = now - timedelta(minutes=window)
        while self._soc_samples and self._soc_samples[0][0] < cutoff:
            self._soc_samples.popleft()

        if soc is not None and soc >= threshold:
            self._full_since = self._full_since or now
        else:
            self._full_since = None

        points = [((t - now).total_seconds() / 60, value)
                  for t, value in self._soc_samples]
        rate = slope(points)
        result = forecast(now=now, soc=soc, rate=rate, sunset=sunset,
                          daylight=daylight, threshold=threshold,
                          full_since=self._full_since)
        if soc is not None and soc < threshold and (
            sun is None or sun.state not in ("above_horizon", "below_horizon")
        ):
            return SunSolarData(None, "unavailable", None, len(points))
        return SunSolarData(result.eta, result.status,
                            rate * 60 if rate is not None else None, len(points))
