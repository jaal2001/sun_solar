"""Resolve and validate battery settings."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, PERCENTAGE
from homeassistant.core import State, valid_entity_id

from .calculation import valid_soc
from .const import (
    CONF_BATTERY_SOC_ENTITY,
    CONF_FULL_THRESHOLD,
    CONF_USE_RECORDER,
    CONF_WINDOW_MINUTES,
    MAX_WINDOW_MINUTES,
    MIN_WINDOW_MINUTES,
    SOC_FULL_THRESHOLD,
    SOC_RATE_WINDOW_MINUTES,
)


def valid_source(entity_id: object) -> bool:
    """Check that the source is a sensor entity ID."""
    return (
        isinstance(entity_id, str)
        and entity_id.startswith("sensor.")
        and valid_entity_id(entity_id)
    )


def is_soc_unit(state: State) -> bool:
    """Accept percent and unitless SOC sensors."""
    return state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) in (None, PERCENTAGE)


@dataclass(frozen=True)
class BatterySettings:
    """Effective settings for one battery, including legacy source options."""

    entity_id: str
    window_minutes: int
    full_threshold: float
    use_recorder: bool

    @classmethod
    def from_entry(cls, entry: ConfigEntry) -> "BatterySettings":
        """Parse stored settings, including options saved by v0.3."""
        config = {**entry.data, **entry.options}
        source = config.get(CONF_BATTERY_SOC_ENTITY)
        raw_window = config.get(CONF_WINDOW_MINUTES, SOC_RATE_WINDOW_MINUTES)
        try:
            window = float(raw_window)
        except (TypeError, ValueError, OverflowError):
            window = None
        threshold = valid_soc(config.get(CONF_FULL_THRESHOLD, SOC_FULL_THRESHOLD))
        recorder = config.get(CONF_USE_RECORDER, False)
        if (
            not valid_source(source)
            or window is None
            or not MIN_WINDOW_MINUTES <= window <= MAX_WINDOW_MINUTES
            or not window.is_integer()
            or threshold is None
            or threshold <= 0
            or not isinstance(recorder, bool)
        ):
            raise ValueError("Invalid battery settings")
        return cls(source, int(window), threshold, recorder)
