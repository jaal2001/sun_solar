"""Sensor platform for the Sun Solar integration."""
from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_SAMPLES_IN_WINDOW, ATTR_SOC_RATE_PERCENT_PER_HOUR, ATTR_STATUS, DOMAIN
from .coordinator import SunSolarCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the battery-full-ETA sensor from a config entry."""
    coordinator: SunSolarCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SunSolarBatteryEtaSensor(coordinator, entry)])


class SunSolarBatteryEtaSensor(CoordinatorEntity[SunSolarCoordinator], SensorEntity):
    """Timestamp entity: when the battery is expected to be full.

    Berechnung: lineare Regression der SOC-Steigung (%/Minute) über die
    letzten 15 Minuten, linear auf 100% hochgerechnet. Kein Umweg über
    Leistung oder Kapazität - der SOC-Sensor liefert die nötige Information
    direkt.

    Reusable in automations, e.g.:
      trigger:
        - platform: template
          value_template: >
            {{ states('sensor.sun_solar_battery_full_eta') not in
               ['unknown', 'unavailable'] and
               now() >= as_datetime(states('sensor.sun_solar_battery_full_eta')) }}
    """

    _attr_has_entity_name = True
    _attr_name = "Battery full ETA"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:battery-clock"

    def __init__(self, coordinator: SunSolarCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_battery_full_eta"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": "Sun Solar (custom)",
        }

    @property
    def native_value(self) -> datetime | None:
        return self.coordinator.data.eta if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            ATTR_STATUS: data.status,
            ATTR_SOC_RATE_PERCENT_PER_HOUR: (
                round(data.soc_rate_percent_per_hour, 2)
                if data.soc_rate_percent_per_hour is not None
                else None
            ),
            ATTR_SAMPLES_IN_WINDOW: data.samples_in_window,
        }
