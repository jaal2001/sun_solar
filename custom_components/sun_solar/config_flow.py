"""Configure Sun Solar batteries and their forecast settings."""

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .calculation import valid_soc
from .const import (
    CONF_BATTERY_SOC_ENTITY,
    CONF_FULL_THRESHOLD,
    CONF_USE_RECORDER,
    CONF_WINDOW_MINUTES,
    DEFAULT_NAME,
    DOMAIN,
    MAX_WINDOW_MINUTES,
    MIN_WINDOW_MINUTES,
    SOC_FULL_THRESHOLD,
    SOC_RATE_WINDOW_MINUTES,
)
from .settings import is_soc_unit, valid_source

BATTERY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(CONF_BATTERY_SOC_ENTITY): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        ),
    }
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_WINDOW_MINUTES, default=SOC_RATE_WINDOW_MINUTES
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=MIN_WINDOW_MINUTES,
                max=MAX_WINDOW_MINUTES,
                step=1,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(
            CONF_FULL_THRESHOLD, default=SOC_FULL_THRESHOLD
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0.1,
                max=100,
                step=0.1,
                unit_of_measurement="%",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_USE_RECORDER, default=False): selector.BooleanSelector(),
    }
)


class SunSolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Add or reconfigure one independently named battery."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> config_entries.OptionsFlow:
        """Create the forecast options flow."""
        return SunSolarOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a battery."""
        return self._battery_form("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Rename a battery or change its SOC source."""
        return self._battery_form(
            "reconfigure", user_input, self._get_reconfigure_entry()
        )

    def _battery_form(
        self,
        step: str,
        user_input: dict[str, Any] | None,
        entry: ConfigEntry | None = None,
    ) -> ConfigFlowResult:
        errors = {}
        current = (
            {**entry.data, **entry.options, CONF_NAME: entry.title}
            if entry
            else {CONF_NAME: DEFAULT_NAME}
        )
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            source = user_input[CONF_BATTERY_SOC_ENTITY]
            state = self.hass.states.get(source) if valid_source(source) else None
            if not name:
                errors[CONF_NAME] = "empty_name"
            if not valid_source(source) or (
                state is not None and not is_soc_unit(state)
            ):
                errors[CONF_BATTERY_SOC_ENTITY] = "invalid_source"
            elif any(
                other is not entry
                and other.options.get(
                    CONF_BATTERY_SOC_ENTITY, other.data.get(CONF_BATTERY_SOC_ENTITY)
                )
                == source
                for other in self._async_current_entries()
            ):
                errors[CONF_BATTERY_SOC_ENTITY] = "duplicate_source"
            if not errors:
                data = {CONF_BATTERY_SOC_ENTITY: source}
                if entry is None:
                    return self.async_create_entry(title=name, data=data)
                options = dict(entry.options)
                options.pop(CONF_BATTERY_SOC_ENTITY, None)
                return self.async_update_reload_and_abort(
                    entry,
                    title=name,
                    data_updates=data,
                    options=options,
                    reload_even_if_entry_is_unchanged=False,
                )
            current.update(user_input)
        return self.async_show_form(
            step_id=step,
            data_schema=self.add_suggested_values_to_schema(BATTERY_SCHEMA, current),
            errors=errors,
        )


class SunSolarOptionsFlow(config_entries.OptionsFlowWithReload):
    """Edit the forecast window, full threshold and optional history."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and save forecast options."""
        current = dict(self.config_entry.options)
        errors = {}
        if user_input is not None:
            window = user_input[CONF_WINDOW_MINUTES]
            threshold = valid_soc(user_input[CONF_FULL_THRESHOLD])
            if not MIN_WINDOW_MINUTES <= window <= MAX_WINDOW_MINUTES or window % 1:
                errors[CONF_WINDOW_MINUTES] = "invalid_window"
            if threshold is None or threshold < 0.1:
                errors[CONF_FULL_THRESHOLD] = "invalid_threshold"
            current.update(user_input)
            if not errors:
                return self.async_create_entry(title="", data=current)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, current),
            errors=errors,
        )
