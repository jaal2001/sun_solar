"""Share a single aggregate forecast across enabled battery entries."""

from collections.abc import Callable

from homeassistant.config_entries import SIGNAL_CONFIG_ENTRY_CHANGED, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .calculation import Forecast, aggregate
from .const import DOMAIN
from .coordinator import SunSolarCoordinator

ETA_UNIQUE_ID = "all_batteries_eta"
FULL_UNIQUE_ID = "all_batteries_full"
UNAVAILABLE = Forecast("unavailable")


class AggregateForecast:
    """Track every configured battery and host one pair of aggregate entities."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.batteries: dict[str, SunSolarCoordinator] = {}
        self.listeners: set[Callable[[], None]] = set()
        self.result = UNAVAILABLE
        self.owner: str | None = None
        self._unsub_entries = async_dispatcher_connect(
            hass, SIGNAL_CONFIG_ENTRY_CHANGED, self._async_entry_changed
        )

    @callback
    def _async_entry_changed(self, _change, entry: ConfigEntry) -> None:
        if entry.domain == DOMAIN:
            self.async_refresh()

    @callback
    def async_refresh(self) -> None:
        """Recompute from every enabled entry, including entries awaiting setup."""
        results = []
        for entry in self.hass.config_entries.async_entries(
            DOMAIN, include_ignore=False, include_disabled=False
        ):
            battery = self.batteries.get(entry.entry_id)
            if (
                battery is None
                or not battery.last_update_success
                or battery.data is None
            ):
                results.append(UNAVAILABLE)
            else:
                results.append(battery.data.forecast)
        result = aggregate(results)
        if result != self.result:
            self.result = result
            for listener in tuple(self.listeners):
                listener()

    @callback
    def async_add(self, entry_id: str, battery: SunSolarCoordinator) -> None:
        """Register a successfully loaded battery."""
        self.batteries[entry_id] = battery
        self.async_refresh()
        self._async_assign_owner()

    @callback
    def async_remove(self, entry_id: str) -> None:
        """Transfer the aggregate entities after the old platforms unload."""
        self.batteries.pop(entry_id)
        if self.owner == entry_id:
            self.owner = None
            self._async_assign_owner()
        self.async_refresh()

    @callback
    def async_close(self) -> None:
        """Stop listening when the last battery unloads."""
        self._unsub_entries()

    @callback
    def _async_assign_owner(self) -> None:
        if self.owner is not None or not self.batteries:
            return
        self.owner = next(iter(self.batteries))
        registry = er.async_get(self.hass)
        for platform, add in self.batteries[self.owner].aggregate_adders.items():
            unique_id = ETA_UNIQUE_ID if platform == "sensor" else FULL_UNIQUE_ID
            entity_id = registry.async_get_entity_id(platform, DOMAIN, unique_id)
            if entity_id is not None:
                registry.async_update_entity(entity_id, config_entry_id=self.owner)
            add(self)


class AggregateEntity(Entity):
    """Subscribe a shared entity to aggregate updates."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, forecast: AggregateForecast) -> None:
        self.forecast = forecast

    async def async_added_to_hass(self) -> None:
        """Subscribe until this platform is unloaded."""
        await super().async_added_to_hass()
        listener = self.async_write_ha_state
        self.forecast.listeners.add(listener)
        self.async_on_remove(lambda: self.forecast.listeners.discard(listener))
