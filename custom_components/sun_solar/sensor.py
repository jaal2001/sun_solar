"""Timestamp sensors for batteries and their aggregate forecast."""

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import SunSolarConfigEntry
from .aggregate import ETA_UNIQUE_ID, UNAVAILABLE, AggregateEntity, AggregateForecast
from .calculation import Forecast
from .const import (
    ATTR_ETA_DISPLAY,
    ATTR_SAMPLES_IN_WINDOW,
    ATTR_SOC_RATE_PERCENT_PER_HOUR,
    ATTR_STATUS,
    DISPLAY_TEXT_FULL,
    DISPLAY_TEXT_UNKNOWN,
    DOMAIN,
)
from .coordinator import SunSolarCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunSolarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add the battery sensor and register the aggregate sensor factory."""
    coordinator = entry.runtime_data
    async_add_entities([SunSolarBatteryEtaSensor(coordinator, entry)])

    def add_aggregate(forecast: AggregateForecast) -> None:
        async_add_entities([SunSolarAggregateEtaSensor(forecast)])

    coordinator.aggregate_adders["sensor"] = add_aggregate


def forecast_attributes(result: Forecast) -> dict[str, str]:
    """Return the stable display contract in Home Assistant's local timezone."""
    display = DISPLAY_TEXT_UNKNOWN
    if result.status == "full":
        display = DISPLAY_TEXT_FULL
    elif result.eta is not None:
        display = dt_util.as_local(result.eta).strftime("%H:%M")
    return {ATTR_STATUS: result.status, ATTR_ETA_DISPLAY: display}


class SunSolarBatteryEtaSensor(CoordinatorEntity[SunSolarCoordinator], SensorEntity):
    """Expected time when this battery reaches its full threshold."""

    _attr_has_entity_name = True
    _attr_translation_key = "battery_full_eta"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:battery-clock"

    def __init__(
        self, coordinator: SunSolarCoordinator, entry: SunSolarConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_battery_full_eta"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Sun Solar",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data.forecast.eta

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        rate = data.soc_rate_percent_per_hour
        return {
            **forecast_attributes(data.forecast if self.available else UNAVAILABLE),
            ATTR_SOC_RATE_PERCENT_PER_HOUR: round(rate, 2)
            if rate is not None
            else None,
            ATTR_SAMPLES_IN_WINDOW: data.samples_in_window,
        }


class SunSolarAggregateEtaSensor(AggregateEntity, SensorEntity):
    """Completion time for the last battery still charging."""

    _attr_unique_id = ETA_UNIQUE_ID
    _attr_translation_key = "all_batteries_eta"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:battery-clock"
    entity_id = "sensor.sun_solar_all_batteries_eta"

    @property
    def native_value(self) -> datetime | None:
        return self.forecast.result.eta

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return forecast_attributes(self.forecast.result)
