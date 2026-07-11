"""Config flow for the Sun Solar integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY_REMAINING_ENTITY,
    CONF_BATTERY_SOC_ENTITY,
    CONF_POWER_ENTITY,
    DEFAULT_NAME,
    DOMAIN,
)


def _build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_POWER_ENTITY, default=defaults.get(CONF_POWER_ENTITY)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_BATTERY_SOC_ENTITY,
                default=defaults.get(CONF_BATTERY_SOC_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Required(
                CONF_BATTERY_REMAINING_ENTITY,
                default=defaults.get(CONF_BATTERY_REMAINING_ENTITY),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
        }
    )


class SunSolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial GUI setup (Settings > Devices & Services > Add Integration)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_NAME, data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=_build_schema(), errors=errors
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> "SunSolarOptionsFlow":
        return SunSolarOptionsFlow()


class SunSolarOptionsFlow(config_entries.OptionsFlow):
    """Handle reconfiguration via the "Configure" button on the integration tile.

    NOTE (Version-Abhängigkeit, bewusst geflaggt statt geraten):
    Ab Home Assistant 2024.12 setzt die Basisklasse `self.config_entry`
    automatisch; ein eigener __init__, der das Attribut überschreibt, ist
    seitdem deprecated. Dieser Code setzt auf dieses (neuere) Verhalten.
    Falls die HA-Version darunter liegt, muss hier ein __init__ ergänzt
    werden, das `self.config_entry = config_entry` speichert.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_build_schema(current)
        )
