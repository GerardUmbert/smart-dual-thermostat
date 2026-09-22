"""Forced-mode select entity per zone.

Mirrors input_select.termostato_virtual_modo_forzado from the original
project. Exposed separately from the climate entity's hvac_mode so
existing dashboards/scripts that expect a plain select (e.g. dashboard
chips) keep working; changing either one keeps the other in sync via the
shared ZoneCoordinator.
"""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, FORCED_MODE_OPTIONS
from .coordinator import ZoneCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = [
        ForcedModeSelect(entry, coordinator)
        for coordinator in data["coordinators"].values()
    ]
    async_add_entities(entities)


class ForcedModeSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "forced_mode"
    _attr_options = FORCED_MODE_OPTIONS
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, coordinator: ZoneCoordinator) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_{coordinator.config.zone_id}_forced_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{coordinator.config.zone_id}")},
        )

    async def async_added_to_hass(self) -> None:
        self._coordinator.on_update.append(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.on_update.remove(self.async_write_ha_state)

    @property
    def current_option(self) -> str:
        return self._coordinator.forced_mode

    async def async_select_option(self, option: str) -> None:
        await self._coordinator.async_set_forced_mode(option)
