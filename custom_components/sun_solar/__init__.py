"""Set up and unload Sun Solar battery entries."""

from pathlib import Path

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .aggregate import AggregateForecast
from .const import DOMAIN
from .coordinator import SunSolarCoordinator
from .settings import BatterySettings

SunSolarConfigEntry = ConfigEntry[SunSolarCoordinator]
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


CARD_URL = "/sun_solar/sun-solar-dashboard-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve and register the bundled dashboard card once."""
    if DATA_EXTRA_MODULE_URL not in hass.data:
        return True

    module = Path(__file__).parent / "www" / "sun-solar-dashboard-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(module), False)]
    )
    integration = await async_get_integration(hass, DOMAIN)
    add_extra_js_url(hass, f"{CARD_URL}?v={integration.version}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SunSolarConfigEntry) -> bool:
    """Validate configuration and set up one battery and its state listeners."""
    try:
        settings = BatterySettings.from_entry(entry)
    except ValueError as err:
        raise ConfigEntryError("Invalid battery settings") from err
    coordinator = SunSolarCoordinator(hass, entry, settings)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    shared = hass.data.get(DOMAIN)
    if shared is None:
        shared = hass.data[DOMAIN] = AggregateForecast(hass)
    shared.async_add(entry.entry_id, coordinator)
    entry.async_on_unload(coordinator.async_add_listener(shared.async_refresh))
    entry.async_on_unload(coordinator.async_watch_inputs())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SunSolarConfigEntry) -> bool:
    """Unload both platforms and release shared state if no batteries remain."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    shared = hass.data[DOMAIN]
    shared.async_remove(entry.entry_id)
    if not shared.batteries:
        shared.async_close()
        del hass.data[DOMAIN]
    return True
