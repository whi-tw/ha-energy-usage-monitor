"""Config flow for Appliance Health Monitor integration."""
from __future__ annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    APPLIANCE_PRESETS,
    APPLIANCE_TYPES,
    CONF_APPLIANCE_NAME,
    CONF_APPLIANCE_TYPE,
    CONF_BASELINE_DRIFT_THRESHOLD,
    CONF_COMPRESSOR_CYCLE_THRESHOLD,
    CONF_CYCLE_ANOMALY_TOLERANCE,
    CONF_DOOR_GRACE_MINUTES,
    CONF_DOOR_OPEN_SENSITIVITY,
    CONF_EXPECTED_DAILY_CYCLES,
    CONF_LEARNING_PERIOD_HOURS,
    CONF_MAX_COMPRESSOR_OFF_HOURS,
    CONF_POWER_SENSOR,
    DEFAULT_COMPRESSOR_THRESHOLD,
    DEFAULT_CYCLE_TOLERANCE,
    DEFAULT_DOOR_GRACE_PERIOD,
    DEFAULT_DOOR_SENSITIVITY,
    DEFAULT_DRIFT_THRESHOLD,
    DEFAULT_EXPECTED_CYCLES,
    DEFAULT_LEARNING_PERIOD,
    DEFAULT_MAX_COMPRESSOR_OFF,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ApplianceHealthMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Appliance Health Monitor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_input: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the power sensor exists
            power_sensor = user_input[CONF_POWER_SENSOR]
            if not self.hass.states.get(power_sensor):
                errors["base"] = "invalid_sensor"
            else:
                # Check if already configured
                await self.async_set_unique_id(
                    f"{DOMAIN}_{user_input[CONF_APPLIANCE_NAME]}"
                )
                self._abort_if_unique_id_configured()

                # Store user input and move to thresholds step
                self._user_input = user_input
                return await self.async_step_thresholds()

        # Show user form
        data_schema = vol.Schema(
            {
                vol.Required(CONF_APPLIANCE_NAME): cv.string,
                vol.Required(CONF_POWER_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="power",
                    )
                ),
                vol.Required(
                    CONF_APPLIANCE_TYPE,
                    default=APPLIANCE_TYPES[0],
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=APPLIANCE_TYPES,
                        translation_key="appliance_type",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_thresholds(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the thresholds configuration step."""
        if user_input is not None:
            # Merge with previous input
            full_data = {**self._user_input, **user_input}

            # Create the config entry
            return self.async_create_entry(
                title=full_data[CONF_APPLIANCE_NAME],
                data=full_data,
            )

        # Get appliance type presets
        appliance_type = self._user_input.get(CONF_APPLIANCE_TYPE)
        presets = APPLIANCE_PRESETS.get(appliance_type, {})

        # Show thresholds form with defaults from presets
        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_LEARNING_PERIOD_HOURS,
                    default=DEFAULT_LEARNING_PERIOD,
                ): vol.All(vol.Coerce(int), vol.Range(min=24, max=168)),
                vol.Optional(
                    CONF_DOOR_OPEN_SENSITIVITY,
                    default=DEFAULT_DOOR_SENSITIVITY,
                ): vol.All(vol.Coerce(float), vol.Range(min=1.5, max=4.0)),
                vol.Optional(
                    CONF_DOOR_GRACE_MINUTES,
                    default=DEFAULT_DOOR_GRACE_PERIOD,
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Optional(
                    CONF_COMPRESSOR_CYCLE_THRESHOLD,
                    default=presets.get(
                        CONF_COMPRESSOR_CYCLE_THRESHOLD, DEFAULT_COMPRESSOR_THRESHOLD
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=100)),
                vol.Optional(
                    CONF_MAX_COMPRESSOR_OFF_HOURS,
                    default=DEFAULT_MAX_COMPRESSOR_OFF,
                ): vol.All(vol.Coerce(int), vol.Range(min=2, max=12)),
                vol.Optional(
                    CONF_BASELINE_DRIFT_THRESHOLD,
                    default=DEFAULT_DRIFT_THRESHOLD,
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=30)),
                vol.Optional(
                    CONF_EXPECTED_DAILY_CYCLES,
                    default=presets.get(
                        CONF_EXPECTED_DAILY_CYCLES, DEFAULT_EXPECTED_CYCLES
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=100)),
                vol.Optional(
                    CONF_CYCLE_ANOMALY_TOLERANCE,
                    default=DEFAULT_CYCLE_TOLERANCE,
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=100)),
            }
        )

        return self.async_show_form(
            step_id="thresholds",
            data_schema=data_schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ApplianceHealthMonitorOptionsFlow(config_entry)


class ApplianceHealthMonitorOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Appliance Health Monitor."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current values (from options if set, otherwise from data)
        current = {**self.config_entry.data, **self.config_entry.options}

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_LEARNING_PERIOD_HOURS,
                    default=current.get(CONF_LEARNING_PERIOD_HOURS, DEFAULT_LEARNING_PERIOD),
                ): vol.All(vol.Coerce(int), vol.Range(min=24, max=168)),
                vol.Optional(
                    CONF_DOOR_OPEN_SENSITIVITY,
                    default=current.get(CONF_DOOR_OPEN_SENSITIVITY, DEFAULT_DOOR_SENSITIVITY),
                ): vol.All(vol.Coerce(float), vol.Range(min=1.5, max=4.0)),
                vol.Optional(
                    CONF_DOOR_GRACE_MINUTES,
                    default=current.get(CONF_DOOR_GRACE_MINUTES, DEFAULT_DOOR_GRACE_PERIOD),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Optional(
                    CONF_COMPRESSOR_CYCLE_THRESHOLD,
                    default=current.get(CONF_COMPRESSOR_CYCLE_THRESHOLD, DEFAULT_COMPRESSOR_THRESHOLD),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=100)),
                vol.Optional(
                    CONF_MAX_COMPRESSOR_OFF_HOURS,
                    default=current.get(CONF_MAX_COMPRESSOR_OFF_HOURS, DEFAULT_MAX_COMPRESSOR_OFF),
                ): vol.All(vol.Coerce(int), vol.Range(min=2, max=12)),
                vol.Optional(
                    CONF_BASELINE_DRIFT_THRESHOLD,
                    default=current.get(CONF_BASELINE_DRIFT_THRESHOLD, DEFAULT_DRIFT_THRESHOLD),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=30)),
                vol.Optional(
                    CONF_EXPECTED_DAILY_CYCLES,
                    default=current.get(CONF_EXPECTED_DAILY_CYCLES, DEFAULT_EXPECTED_CYCLES),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=100)),
                vol.Optional(
                    CONF_CYCLE_ANOMALY_TOLERANCE,
                    default=current.get(CONF_CYCLE_ANOMALY_TOLERANCE, DEFAULT_CYCLE_TOLERANCE),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=100)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )
