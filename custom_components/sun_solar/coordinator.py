"""Sample each battery's SOC and forecast its solar charge completion."""

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SUN_EVENT_SUNRISE
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .calculation import Forecast, forecast, slope, valid_soc
from .const import DOMAIN, SUN_ENTITY_ID, UPDATE_INTERVAL_SECONDS
from .settings import BatterySettings, is_soc_unit

if TYPE_CHECKING:
    from .aggregate import AggregateForecast

_LOGGER = logging.getLogger(__name__)
SAMPLE_INTERVAL = timedelta(seconds=UPDATE_INTERVAL_SECONDS)


@dataclass(frozen=True)
class SunSolarData:
    """Forecast and diagnostics for an individual battery."""

    forecast: Forecast
    soc_rate_percent_per_hour: float | None
    samples_in_window: int


class SunSolarCoordinator(DataUpdateCoordinator[SunSolarData]):
    """Maintain an independent rolling SOC history for a config entry."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, settings: BatterySettings
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SAMPLE_INTERVAL,
            always_update=False,
        )
        self.settings = settings
        self.aggregate_adders: dict[str, Callable[["AggregateForecast"], None]] = {}
        self._samples: deque[tuple[datetime, float]] = deque()
        self._full_since: datetime | None = None
        self._window = timedelta(minutes=settings.window_minutes)

    @callback
    def async_watch_inputs(self) -> Callable[[], None]:
        """Refresh immediately when daylight or the source changes."""
        return async_track_state_change_event(
            self.hass,
            [self.settings.entity_id, SUN_ENTITY_ID],
            self._async_input_changed,
        )

    @callback
    def _async_input_changed(self, _event: Event[EventStateChangedData]) -> None:
        data = self._sample()
        if data != self.data or not self.last_update_success:
            self.async_set_updated_data(data)

    async def _async_setup(self) -> None:
        """Seed recent daylight samples from Recorder when enabled."""
        if not self.settings.use_recorder:
            return
        now = dt_util.utcnow()
        sun = self.hass.states.get(SUN_ENTITY_ID)
        if sun is None or sun.state != "above_horizon":
            return
        sunrise = get_astral_event_date(self.hass, SUN_EVENT_SUNRISE, now)
        if sunrise is None or sunrise >= now:
            return

        # Import only when Recorder is loaded.
        if "recorder" not in self.hass.config.components:
            return
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.history import get_significant_states

        start = max(sunrise, now - self._window)
        entity_id = self.settings.entity_id
        try:
            recorder = get_instance(self.hass)
            if recorder.entity_filter is not None and not recorder.entity_filter(
                entity_id
            ):
                return
            async with asyncio.timeout(5):
                history = await recorder.async_add_executor_job(
                    partial(
                        get_significant_states,
                        self.hass,
                        start,
                        now,
                        [entity_id],
                        significant_changes_only=False,
                    )
                )
            sample_time = start
            value = None
            for state in history.get(entity_id, ()):
                while sample_time < min(state.last_updated, now):
                    if value is not None:
                        self._samples.append((sample_time, value))
                    sample_time += SAMPLE_INTERVAL
                value = read_soc(state)
                if value is None:
                    self._samples.clear()
            # A stale history ending at a different SOC can create a false
            # jump on startup. Collect live samples when the readings disagree.
            if value is None or value != read_soc(self.hass.states.get(entity_id)):
                self._samples.clear()
                return
            while sample_time < now:
                self._samples.append((sample_time, value))
                sample_time += SAMPLE_INTERVAL
        except Exception:
            self._samples.clear()
            _LOGGER.debug(
                "Recorder history unavailable; collecting live SOC", exc_info=True
            )

    async def _async_update_data(self) -> SunSolarData:
        return self._sample()

    @callback
    def _sample(self) -> SunSolarData:
        now = dt_util.utcnow()
        soc = read_soc(self.hass.states.get(self.settings.entity_id))
        sun = self.hass.states.get(SUN_ENTITY_ID)
        daylight = sun is not None and sun.state == "above_horizon"
        raw_sunset = sun.attributes.get("next_setting") if sun is not None else None
        sunset = (
            dt_util.parse_datetime(raw_sunset)
            if isinstance(raw_sunset, str)
            else raw_sunset
        )
        if not isinstance(sunset, datetime) or sunset.utcoffset() is None:
            sunset = None

        if (
            soc is None
            or not daylight
            or sunset is None
            or sunset <= now
            or (self._samples and now - self._samples[-1][0] > SAMPLE_INTERVAL * 3)
        ):
            self._samples.clear()

        if soc is not None and daylight and sunset is not None and sunset > now:
            if not self._samples or now - self._samples[-1][0] >= SAMPLE_INTERVAL:
                self._samples.append((now, soc))

        cutoff = now - self._window
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

        threshold = self.settings.full_threshold
        if soc is not None and soc >= threshold:
            self._full_since = self._full_since or now
        else:
            self._full_since = None

        rate = slope(
            [((t - now).total_seconds() / 60, value) for t, value in self._samples]
        )
        result = forecast(
            now=now,
            soc=soc,
            rate=rate,
            sunset=sunset,
            daylight=daylight,
            threshold=threshold,
            full_since=self._full_since,
        )
        if result.status != "full" and (
            sun is None or sun.state not in ("above_horizon", "below_horizon")
        ):
            result = Forecast("unavailable")
        return SunSolarData(
            result, rate * 60 if rate is not None else None, len(self._samples)
        )


def read_soc(state: State | None) -> float | None:
    """Read a percentage from a live or recorded state."""
    if state is None or not is_soc_unit(state):
        return None
    return valid_soc(state.state)
