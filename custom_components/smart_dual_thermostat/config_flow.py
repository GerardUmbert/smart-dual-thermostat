"""Config flow: hub setup, then a repeatable zone-pairing wizard.

Flow shape:
  user (hub-level options: outdoor sensor, notify service, away entity,
        season mode) -> zone (repeatable: name + pair heat/cool actuators
        + comfort ranges) -> zone_add_another (loop or finish)

Each zone pairs at most one heat actuator and one cool actuator (plus
optional fan entities for the cool side), covering the "one thermostat
for the whole house" case (single zone) as well as "one heat+cool pair
per floor" (multiple zones) without treating either as a special case.
"""
from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_AWAY_ENTITY,
    CONF_COOL_ENTITY,
    CONF_COOL_FAN_ENTITIES,
    CONF_COOL_MAX,
    CONF_COOL_MIN,
    CONF_COOL_OFFSET,
    CONF_COOL_RELAXED,
    CONF_COOL_SCALE,
    CONF_HEAT_ENTITY,
    CONF_HEAT_MAX,
    CONF_HEAT_MIN,
    CONF_HEAT_OFFSET,
    CONF_HEAT_RELAXED,
    CONF_HEAT_SCALE,
    CONF_NOTIFY_SERVICE,
    CONF_OUTDOOR_SENSOR,
    CONF_SEASON_MODE,
    CONF_ZONE_ID,
    CONF_ZONE_INDOOR_SENSOR,
    CONF_ZONE_NAME,
    CONF_ZONE_OUTDOOR_SENSOR_OVERRIDE,
    CONF_ZONES,
    DEFAULT_COOL_MAX,
    DEFAULT_COOL_MIN,
    DEFAULT_COOL_RELAXED,
    DEFAULT_HEAT_MAX,
    DEFAULT_HEAT_MIN,
    DEFAULT_HEAT_RELAXED,
    DEFAULT_SEASON_MODE,
    DOMAIN,
    SEASON_MODE_CUSTOM_MONTHS,
    SEASON_MODE_HEMISPHERE,
    SEASON_MODE_TEMP_ONLY,
)


def _hub_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(
                CONF_OUTDOOR_SENSOR, default=defaults.get(CONF_OUTDOOR_SENSOR)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "weather"])
            ),
            vol.Optional(
                CONF_SEASON_MODE, default=defaults.get(CONF_SEASON_MODE, DEFAULT_SEASON_MODE)
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        SEASON_MODE_HEMISPHERE,
                        SEASON_MODE_CUSTOM_MONTHS,
                        SEASON_MODE_TEMP_ONLY,
                    ],
                    translation_key="season_mode",
                )
            ),
            vol.Optional(
                CONF_NOTIFY_SERVICE, default=defaults.get(CONF_NOTIFY_SERVICE)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="notify")
            ),
            vol.Optional(
                CONF_AWAY_ENTITY, default=defaults.get(CONF_AWAY_ENTITY)
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["input_boolean", "binary_sensor"])
            ),
        }
    )


def _zone_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_ZONE_NAME, default=defaults.get(CONF_ZONE_NAME, "")): str,
            vol.Optional(CONF_HEAT_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["climate", "switch"])
            ),
            vol.Optional(CONF_HEAT_SCALE, default=1.0): vol.Coerce(float),
            vol.Optional(CONF_HEAT_OFFSET, default=0.0): vol.Coerce(float),
            vol.Optional(CONF_COOL_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["climate", "switch"])
            ),
            vol.Optional(CONF_COOL_SCALE, default=1.0): vol.Coerce(float),
            vol.Optional(CONF_COOL_OFFSET, default=0.0): vol.Coerce(float),
            vol.Optional(CONF_COOL_FAN_ENTITIES): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="fan", multiple=True)
            ),
            vol.Optional(CONF_ZONE_INDOOR_SENSOR): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            ),
            vol.Optional(CONF_ZONE_OUTDOOR_SENSOR_OVERRIDE): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["sensor", "weather"])
            ),
            vol.Optional(CONF_COOL_MIN, default=DEFAULT_COOL_MIN): vol.Coerce(float),
            vol.Optional(CONF_COOL_RELAXED, default=DEFAULT_COOL_RELAXED): vol.Coerce(float),
            vol.Optional(CONF_COOL_MAX, default=DEFAULT_COOL_MAX): vol.Coerce(float),
            vol.Optional(CONF_HEAT_MIN, default=DEFAULT_HEAT_MIN): vol.Coerce(float),
            vol.Optional(CONF_HEAT_RELAXED, default=DEFAULT_HEAT_RELAXED): vol.Coerce(float),
            vol.Optional(CONF_HEAT_MAX, default=DEFAULT_HEAT_MAX): vol.Coerce(float),
        }
    )


class SmartDualThermostatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._hub_data: dict[str, Any] = {}
        self._zones: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            self._hub_data = user_input
            return await self.async_step_zone()

        return self.async_show_form(step_id="user", data_schema=_hub_schema({}))

    async def async_step_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_HEAT_ENTITY) and not user_input.get(CONF_COOL_ENTITY):
                errors["base"] = "zone_needs_actuator"
            else:
                zone = dict(user_input)
                zone[CONF_ZONE_ID] = str(uuid.uuid4())[:8]
                self._zones.append(zone)
                return await self.async_step_zone_add_another()

        return self.async_show_form(
            step_id="zone", data_schema=_zone_schema({}), errors=errors
        )

    async def async_step_zone_add_another(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            if user_input.get("add_another"):
                return await self.async_step_zone()
            return self._async_create_entry()

        return self.async_show_form(
            step_id="zone_add_another",
            data_schema=vol.Schema({vol.Required("add_another", default=False): bool}),
            description_placeholders={"zone_count": str(len(self._zones))},
        )

    def _async_create_entry(self) -> config_entries.ConfigFlowResult:
        data = {**self._hub_data, CONF_ZONES: self._zones}
        title = (
            self._zones[0][CONF_ZONE_NAME]
            if len(self._zones) == 1
            else f"Smart Dual Thermostat ({len(self._zones)} zones)"
        )
        return self.async_create_entry(title=title, data=data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmartDualThermostatOptionsFlow:
        return SmartDualThermostatOptionsFlow(config_entry)


class SmartDualThermostatOptionsFlow(config_entries.OptionsFlow):
    """Edit hub settings or add a new zone to an existing entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._zones: list[dict[str, Any]] = list(config_entry.data.get(CONF_ZONES, []))

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            new_data = {**self._config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
            return await self.async_step_add_zone()

        return self.async_show_form(
            step_id="init", data_schema=_hub_schema(self._config_entry.data)
        )

    async def async_step_add_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            if user_input.get("add_zone"):
                return await self.async_step_zone()
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_zone",
            data_schema=vol.Schema({vol.Required("add_zone", default=False): bool}),
        )

    async def async_step_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_HEAT_ENTITY) and not user_input.get(CONF_COOL_ENTITY):
                errors["base"] = "zone_needs_actuator"
            else:
                zone = dict(user_input)
                zone[CONF_ZONE_ID] = str(uuid.uuid4())[:8]
                self._zones.append(zone)
                new_data = {**self._config_entry.data, CONF_ZONES: self._zones}
                self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="zone", data_schema=_zone_schema({}), errors=errors
        )
