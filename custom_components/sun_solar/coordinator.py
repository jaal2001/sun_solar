"""Coordinator that computes the battery-full ETA for the Sun Solar integration.

Ansatz: statt Leistung + Kapazität zu verrechnen, wird direkt die Steigung
des SOC (%/Minute) über ein 15-Minuten-Fenster per linearer Regression
bestimmt und linear bis 100% hochgerechnet. Braucht nur eine Entity.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BATTERY_SOC_ENTITY,
    DOMAIN,
    MIN_SOC_RATE_PERCENT_PER_MIN,
    SOC_FULL_THRESHOLD,
    SOC_RATE_WINDOW_MINUTES,
    STATUS_CHARGING,
    STATUS_FULL,
    STATUS_NOT_CHARGING,
    STATUS_UNAVAILABLE,
    UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

_UNUSABLE_STATES = {"unknown", "unavailable", "", None}


@dataclass
class SunSolarData:
    """Result of one coordinator update cycle."""

    eta: datetime | None
    status: str
    soc_rate_percent_per_hour: float | None
    samples_in_window: int


def _to_float(state_value: str | None) -> float | None:
    if state_value in _UNUSABLE_STATES:
        return None
    try:
        return float(state_value)
    except (TypeError, ValueError):
        return None


def _linear_regression_slope(points: list[tuple[float, float]]) -> float | None:
    """Least-squares slope (y per x) über gegebene (x, y)-Punkte.

    Robuster gegen einzelne verrauschte/quantisierte SOC-Werte als eine
    reine Zwei-Punkt-Differenz (erster/letzter Sample).
    """
    n = len(points)
    if n < 2:
        return None
    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in points)
    denominator = sum((x - mean_x) ** 2 for x, _ in points)
    if denominator == 0:
        return None
    return numerator / denominator


class SunSolarCoordinator(DataUpdateCoordinator[SunSolarData]):
    """Samples the SOC entity every UPDATE_INTERVAL_SECONDS and keeps a
    rolling buffer used to compute the SOC-Steigung über die letzten
    SOC_RATE_WINDOW_MINUTES Minuten.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self._entry = entry
        # deque of (timestamp, soc_percent)
        self._soc_samples: deque[tuple[datetime, float]] = deque()

    def _config(self, key: str) -> Any:
        # Options override the initial data set at config_flow time,
        # this is what makes the "Configure" GUI dialog actually take effect.
        return self._entry.options.get(key, self._entry.data.get(key))

    def _read_soc(self) -> float | None:
        entity_id = self._config(CONF_BATTERY_SOC_ENTITY)
        state = self.hass.states.get(entity_id)
        if state is None or state.state in _UNUSABLE_STATES:
            return None
        return _to_float(state.state)

    def _prune_samples(self, now: datetime) -> None:
        cutoff = now - timedelta(minutes=SOC_RATE_WINDOW_MINUTES)
        while self._soc_samples and self._soc_samples[0][0] < cutoff:
            self._soc_samples.popleft()

    def _soc_rate_percent_per_min(self, now: datetime) -> tuple[float | None, int]:
        """Returns (slope_percent_per_minute, sample_count)."""
        if len(self._soc_samples) < 2:
            return None, len(self._soc_samples)
        points = [
            ((t - now).total_seconds() / 60, soc) for t, soc in self._soc_samples
        ]
        slope = _linear_regression_slope(points)
        return slope, len(self._soc_samples)

    async def _async_update_data(self) -> SunSolarData:
        now = dt_util.utcnow()

        soc = self._read_soc()
        if soc is not None:
            self._soc_samples.append((now, soc))
        self._prune_samples(now)

        if soc is None:
            return SunSolarData(
                eta=None,
                status=STATUS_UNAVAILABLE,
                soc_rate_percent_per_hour=None,
                samples_in_window=len(self._soc_samples),
            )

        if soc >= SOC_FULL_THRESHOLD:
            return SunSolarData(
                eta=now,
                status=STATUS_FULL,
                soc_rate_percent_per_hour=0.0,
                samples_in_window=len(self._soc_samples),
            )

        slope_per_min, sample_count = self._soc_rate_percent_per_min(now)

        if slope_per_min is None or slope_per_min < MIN_SOC_RATE_PERCENT_PER_MIN:
            return SunSolarData(
                eta=None,
                status=STATUS_NOT_CHARGING,
                soc_rate_percent_per_hour=(
                    slope_per_min * 60 if slope_per_min is not None else None
                ),
                samples_in_window=sample_count,
            )

        minutes_left = (100 - soc) / slope_per_min
        if minutes_left <= 0 or minutes_left > 24 * 60:
            return SunSolarData(
                eta=None,
                status=STATUS_CHARGING,
                soc_rate_percent_per_hour=slope_per_min * 60,
                samples_in_window=sample_count,
            )

        eta = now + timedelta(minutes=minutes_left)
        return SunSolarData(
            eta=eta,
            status=STATUS_CHARGING,
            soc_rate_percent_per_hour=slope_per_min * 60,
            samples_in_window=sample_count,
        )
