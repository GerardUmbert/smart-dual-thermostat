"""Editable comfort-range entities per zone.

Mirrors the 6 input_number range helpers from the original project
(cool/heat x min/relaxed/max), exposed as Number entities so each zone's
ranges are editable live from a dashboard without going back into the
integration's Options Flow.
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ZoneCoordinator


@dataclass(frozen=True)
class RangeField:
    key: str
    translation_key: str
    min_value: float
    max_value: float


RANGE_FIELDS = [
    RangeField("cool_min", "cool_min", 10, 35),
    RangeField("cool_relaxed", "cool_relaxed", 10, 35),
    RangeField("cool_max", "cool_max", 10, 35),
    RangeField("heat_min", "heat_min", 10, 35),
    RangeField("heat_relaxed", "heat_relaxed", 10, 35),
    RangeField("heat_max", "heat_max", 10, 35),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    entities = [
        ComfortRangeNumber(entry, coordinator, field)
        for coordinator in data["coordinators"].values()
        for field in RANGE_FIELDS
    ]
    async_add_entities(entities)


class ComfortRangeNumber(NumberEntity):
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "°C"
    _attr_native_step = 0.5
    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, coordinator: ZoneCoordinator, field: RangeField) -> None:
        self._coordinator = coordinator
        self._field = field
        self._attr_translation_key = field.translation_key
        self._attr_unique_id = f"{entry.entry_id}_{coordinator.config.zone_id}_{field.key}"
        self._attr_native_min_value = field.min_value
        self._attr_native_max_value = field.max_value
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{coordinator.config.zone_id}")},
        )

    async def async_added_to_hass(self) -> None:
        self._coordinator.on_update.append(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.on_update.remove(self.async_write_ha_state)

    @property
    def native_value(self) -> float:
        return getattr(self._coordinator.config.comfort, self._field.key)

    async def async_set_native_value(self, value: float) -> None:
        setattr(self._coordinator.config.comfort, self._field.key, value)
        self.async_write_ha_state()
