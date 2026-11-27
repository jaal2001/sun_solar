"""Expose whether all configured batteries have reached their threshold."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SunSolarConfigEntry
from .aggregate import FULL_UNIQUE_ID, AggregateEntity, AggregateForecast


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SunSolarConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Register the factory for the single aggregate binary sensor."""

    def add_aggregate(forecast: AggregateForecast) -> None:
        async_add_entities([SunSolarAllFullSensor(forecast)])

    entry.runtime_data.aggregate_adders["binary_sensor"] = add_aggregate


class SunSolarAllFullSensor(AggregateEntity, BinarySensorEntity):
    """Report on only when every battery is confirmed full."""

    _attr_unique_id = FULL_UNIQUE_ID
    _attr_translation_key = "all_batteries_full"
    entity_id = "binary_sensor.sun_solar_all_batteries_full"
    _attr_icon = "mdi:battery-check"

    @property
    def is_on(self) -> bool:
        return self.forecast.result.status == "full"
