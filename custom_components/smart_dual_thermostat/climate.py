"""Expose each zone as a native ClimateEntity.

This is what makes the integration usable without a custom Lovelace card:
HA's built-in thermostat card, voice assistants, and any automation that
targets a climate.* entity all work against this out of the box. HVAC_MODE
AUTO maps to the original "single dial decides heat vs cool" behavior;
HEAT/COOL map to forcing that mode (same as the forced-mode select); OFF
maps to the panic-button shutdown.
"""
from __future__ import annotations

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DECIDED_MODE_COOL,
    DECIDED_MODE_HEAT,
    DOMAIN,
    FORCED_MODE_AUTO,
    FORCED_MODE_COOL,
    FORCED_MODE_HEAT,
)
from .coordinator import ZoneCoordinator

HVAC_MODE_TO_FORCED = {
    HVACMode.AUTO: FORCED_MODE_AUTO,
    HVACMode.HEAT: FORCED_MODE_HEAT,
    HVACMode.COOL: FORCED_MODE_COOL,
}
FORCED_TO_HVAC_MODE = {v: k for k, v in HVAC_MODE_TO_FORCED.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = [
        SmartDualThermostatZone(entry, coordinator)
        for coordinator in data["coordinators"].values()
    ]
    async_add_entities(entities)


class SmartDualThermostatZone(ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = "°C"
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.AUTO, HVACMode.HEAT, HVACMode.COOL]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, coordinator: ZoneCoordinator) -> None:
        self._entry = entry
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_{coordinator.config.zone_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{coordinator.config.zone_id}")},
            name=coordinator.config.name,
            manufacturer="Smart Dual Thermostat",
        )
        self._attr_min_temp = min(
            coordinator.config.comfort.heat_min, coordinator.config.comfort.cool_min
        )
        self._attr_max_temp = max(
            coordinator.config.comfort.heat_max, coordinator.config.comfort.cool_max
        )
        self._attr_target_temperature_step = 0.5

    async def async_added_to_hass(self) -> None:
        self._coordinator.on_update.append(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.on_update.remove(self._handle_coordinator_update)

    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def current_temperature(self) -> float | None:
        return self._coordinator._indoor_temperature()  # noqa: SLF001 - internal, same module family

    @property
    def target_temperature(self) -> float | None:
        return self._coordinator.desired

    @property
    def hvac_mode(self) -> HVACMode:
        if not self._coordinator.active:
            return HVACMode.OFF
        return FORCED_TO_HVAC_MODE.get(self._coordinator.forced_mode, HVACMode.AUTO)

    @property
    def hvac_action(self) -> HVACAction | None:
        if not self._coordinator.active:
            return HVACAction.OFF
        mode = self._coordinator._effective_mode()  # noqa: SLF001
        if mode == DECIDED_MODE_HEAT:
            return HVACAction.HEATING
        if mode == DECIDED_MODE_COOL:
            return HVACAction.COOLING
        return HVACAction.IDLE

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")
        if temperature is None:
            return
        await self._coordinator.async_set_desired(float(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self._coordinator.async_turn_off()
            return
        forced = HVAC_MODE_TO_FORCED.get(hvac_mode, FORCED_MODE_AUTO)
        if not self._coordinator.active:
            self._coordinator.active = True
        await self._coordinator.async_set_forced_mode(forced)
