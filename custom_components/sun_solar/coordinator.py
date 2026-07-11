"""Coordinator that computes the battery-full ETA for the Sun Solar integration."""
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
    AVERAGE_WINDOW_MINUTES,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_BATTERY_SOC_ENTITY,
    CONF_POWER_ENTITY,
    DOMAIN,
    MIN_POWER_FOR_ETA_W,
    SOC_FULL_THRESHOLD,
    STATUS_CHARGING,
    STATUS_FULL,
    STATUS_NO_PRODUCTION,
    STATUS_UNAVAILABLE,
    UPDATE_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

# States that mean "this entity currently has no usable numeric value".
_UNUSABLE_STATES = {"unknown", "unavailable", "", None}


@dataclass
class SunSolarData:
    """Result of one coordinator update cycle."""

    eta: datetime | None
    status: str
    average_power_w: float | None
    remaining_to_charge_kwh: float | None


def _to_float(state_value: str | None) -> float | None:
    if state_value in _UNUSABLE_STATES:
        return None
    try:
        return float(state_value)
    except (TypeError, ValueError):
        return None


class SunSolarCoordinator(DataUpdateCoordinator[SunSolarData]):
    """Samples the power entity every UPDATE_INTERVAL_SECONDS and keeps a
    rolling buffer used to compute the average charging power over the last
    AVERAGE_WINDOW_MINUTES minutes, mirroring the logic that used to live in
    the JavaScript Lovelace card.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self._entry = entry
        # deque of (timestamp, watts)
        self._power_samples: deque[tuple[datetime, float]] = deque()

    def _config(self, key: str) -> Any:
        # Options override the initial data set at config_flow time,
        # this is what makes the "Configure" GUI dialog actually take effect.
        return self._entry.options.get(key, self._entry.data.get(key))

    def _read_power_watts(self) -> float | None:
        entity_id = self._config(CONF_POWER_ENTITY)
        state = self.hass.states.get(entity_id)
        if state is None or state.state in _UNUSABLE_STATES:
            return None
        value = _to_float(state.state)
        if value is None:
            return None
        unit = (state.attributes.get("unit_of_measurement") or "W").lower()
        if unit == "kw":
            return value * 1000
        return value

    def _prune_samples(self, now: datetime) -> None:
        cutoff = now - timedelta(minutes=AVERAGE_WINDOW_MINUTES)
        while self._power_samples and self._power_samples[0][0] < cutoff:
            self._power_samples.popleft()

    def _average_power_w(self) -> float | None:
        if not self._power_samples:
            return None
        total = sum(watts for _, watts in self._power_samples)
        avg = total / len(self._power_samples)
        return avg if avg > 0 else None

    async def _async_update_data(self) -> SunSolarData:
        now = dt_util.utcnow()

        power_w = self._read_power_watts()
        if power_w is not None:
            self._power_samples.append((now, power_w))
        self._prune_samples(now)

        soc = _to_float(
            getattr(
                self.hass.states.get(self._config(CONF_BATTERY_SOC_ENTITY)),
                "state",
                None,
            )
        )
        # Feste, in der GUI konfigurierte Kapazität (kWh) statt einer Entity -
        # der SOC kommt bereits normiert vom BMS, SoH-Alterung wird dort
        # bereits eingerechnet und muss hier nicht nochmal berücksichtigt
        # werden (siehe Diskussion vom 11.07.2026).
        capacity_kwh = _to_float(self._config(CONF_BATTERY_CAPACITY_KWH))

        if soc is None or capacity_kwh is None:
            return SunSolarData(
                eta=None,
                status=STATUS_UNAVAILABLE,
                average_power_w=self._average_power_w(),
                remaining_to_charge_kwh=None,
            )

        if soc >= SOC_FULL_THRESHOLD:
            return SunSolarData(
                eta=now,
                status=STATUS_FULL,
                average_power_w=self._average_power_w(),
                remaining_to_charge_kwh=0.0,
            )

        to_charge_kwh = capacity_kwh * (1 - soc / 100)
        avg_w = self._average_power_w()

        if avg_w is None or avg_w < MIN_POWER_FOR_ETA_W:
            return SunSolarData(
                eta=None,
                status=STATUS_NO_PRODUCTION,
                average_power_w=avg_w,
                remaining_to_charge_kwh=to_charge_kwh,
            )

        minutes_left = (to_charge_kwh * 1000 / avg_w) * 60
        if minutes_left <= 0 or minutes_left > 24 * 60:
            return SunSolarData(
                eta=None,
                status=STATUS_CHARGING,
                average_power_w=avg_w,
                remaining_to_charge_kwh=to_charge_kwh,
            )

        eta = now + timedelta(minutes=minutes_left)
        return SunSolarData(
            eta=eta,
            status=STATUS_CHARGING,
            average_power_w=avg_w,
            remaining_to_charge_kwh=to_charge_kwh,
        )
