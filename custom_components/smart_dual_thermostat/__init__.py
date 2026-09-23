"""Smart Dual Thermostat integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_AWAY_ENTITY,
    CONF_COOL_ENTITY,
    CONF_COOL_ENTITY_DOMAIN,
    CONF_COOL_FAN_ENTITIES,
    CONF_COOL_HVAC_MODE,
    CONF_COOL_MAX,
    CONF_COOL_MIN,
    CONF_COOL_OFFSET,
    CONF_COOL_RELAXED,
    CONF_COOL_SCALE,
    CONF_COOL_SEASON_HEAT_OVERRIDE_BELOW,
    CONF_HEAT_ENTITY,
    CONF_HEAT_ENTITY_DOMAIN,
    CONF_HEAT_HVAC_MODE,
    CONF_HEAT_MAX,
    CONF_HEAT_MIN,
    CONF_HEAT_OFFSET,
    CONF_HEAT_RELAXED,
    CONF_HEAT_SCALE,
    CONF_HEAT_SEASON_COOL_OVERRIDE_ABOVE,
    CONF_MONTHS_COOL,
    CONF_MONTHS_HEAT,
    CONF_NEUTRAL_COOL_ABOVE,
    CONF_NEUTRAL_HEAT_BELOW,
    CONF_NOTIFY_SERVICE,
    CONF_OUTDOOR_SENSOR,
    CONF_SEASON_MODE,
    CONF_COMBINED_OFFSET,
    CONF_COMBINED_SCALE,
    CONF_ZONE_COMBINED_ENTITY,
    CONF_ZONE_DISPLAY_ENTITY,
    CONF_ZONE_ID,
    CONF_ZONE_INDOOR_SENSOR,
    CONF_ZONE_NAME,
    CONF_ZONE_OUTDOOR_SENSOR_OVERRIDE,
    CONF_ZONE_TEMP_STEP,
    CONF_ZONES,
    DEFAULT_COOL_SEASON_HEAT_OVERRIDE_BELOW,
    DEFAULT_HEAT_SEASON_COOL_OVERRIDE_ABOVE,
    DEFAULT_NEUTRAL_COOL_ABOVE,
    DEFAULT_NEUTRAL_HEAT_BELOW,
    DEFAULT_SEASON_MODE,
    DEFAULT_TEMP_STEP_CELSIUS,
    DOMAIN,
    FORCED_MODE_AUTO,
    PLATFORMS,
)
from .coordinator import ActuatorConfig, ComfortRange, ZoneConfig, ZoneCoordinator
from .quirks import Correction


def _build_zone_coordinator(hass: HomeAssistant, entry: ConfigEntry, zone_data: dict) -> ZoneCoordinator:
    heat = ActuatorConfig(
        entity_id=zone_data.get(CONF_HEAT_ENTITY),
        entity_domain=zone_data.get(CONF_HEAT_ENTITY_DOMAIN, "climate"),
        hvac_mode=zone_data.get(CONF_HEAT_HVAC_MODE, "heat"),
        correction=Correction(
            scale=zone_data.get(CONF_HEAT_SCALE, 1.0),
            offset=zone_data.get(CONF_HEAT_OFFSET, 0.0),
        ),
    )
    cool = ActuatorConfig(
        entity_id=zone_data.get(CONF_COOL_ENTITY),
        entity_domain=zone_data.get(CONF_COOL_ENTITY_DOMAIN, "climate"),
        hvac_mode=zone_data.get(CONF_COOL_HVAC_MODE, "cool"),
        correction=Correction(
            scale=zone_data.get(CONF_COOL_SCALE, 1.0),
            offset=zone_data.get(CONF_COOL_OFFSET, 0.0),
        ),
    )
    comfort = ComfortRange(
        cool_min=zone_data[CONF_COOL_MIN],
        cool_relaxed=zone_data[CONF_COOL_RELAXED],
        cool_max=zone_data[CONF_COOL_MAX],
        heat_min=zone_data[CONF_HEAT_MIN],
        heat_relaxed=zone_data[CONF_HEAT_RELAXED],
        heat_max=zone_data[CONF_HEAT_MAX],
    )
    combined_entity_id = zone_data.get(CONF_ZONE_COMBINED_ENTITY)
    combined = (
        ActuatorConfig(
            entity_id=combined_entity_id,
            entity_domain="climate",
            correction=Correction(
                scale=zone_data.get(CONF_COMBINED_SCALE, 1.0),
                offset=zone_data.get(CONF_COMBINED_OFFSET, 0.0),
            ),
        )
        if combined_entity_id
        else None
    )
    zone_config = ZoneConfig(
        zone_id=zone_data[CONF_ZONE_ID],
        name=zone_data[CONF_ZONE_NAME],
        heat=heat,
        cool=cool,
        cool_fan_entities=zone_data.get(CONF_COOL_FAN_ENTITIES, []),
        comfort=comfort,
        indoor_sensor=zone_data.get(CONF_ZONE_INDOOR_SENSOR),
        outdoor_sensor=zone_data.get(CONF_ZONE_OUTDOOR_SENSOR_OVERRIDE),
        temp_step=zone_data.get(CONF_ZONE_TEMP_STEP, DEFAULT_TEMP_STEP_CELSIUS),
        display_entity=zone_data.get(CONF_ZONE_DISPLAY_ENTITY),
        combined=combined,
    )

    return ZoneCoordinator(
        hass,
        zone_config,
        forced_mode=FORCED_MODE_AUTO,
        default_outdoor_sensor=entry.data.get(CONF_OUTDOOR_SENSOR),
        season_mode=entry.data.get(CONF_SEASON_MODE, DEFAULT_SEASON_MODE),
        # SelectSelector(multiple=True) stores its options as strings.
        custom_cool_months=[int(m) for m in entry.data.get(CONF_MONTHS_COOL, [])],
        custom_heat_months=[int(m) for m in entry.data.get(CONF_MONTHS_HEAT, [])],
        cool_season_heat_override_below=entry.data.get(
            CONF_COOL_SEASON_HEAT_OVERRIDE_BELOW, DEFAULT_COOL_SEASON_HEAT_OVERRIDE_BELOW
        ),
        heat_season_cool_override_above=entry.data.get(
            CONF_HEAT_SEASON_COOL_OVERRIDE_ABOVE, DEFAULT_HEAT_SEASON_COOL_OVERRIDE_ABOVE
        ),
        neutral_cool_above=entry.data.get(CONF_NEUTRAL_COOL_ABOVE, DEFAULT_NEUTRAL_COOL_ABOVE),
        neutral_heat_below=entry.data.get(CONF_NEUTRAL_HEAT_BELOW, DEFAULT_NEUTRAL_HEAT_BELOW),
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    zones_data = entry.data.get(CONF_ZONES, [])
    coordinators: dict[str, ZoneCoordinator] = {}

    for zone_data in zones_data:
        coordinator = _build_zone_coordinator(hass, entry, zone_data)
        coordinator.async_setup()
        coordinators[zone_data[CONF_ZONE_ID]] = coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinators": coordinators,
        "away_entity": entry.data.get(CONF_AWAY_ENTITY),
        "notify_service": entry.data.get(CONF_NOTIFY_SERVICE),
    }

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        for coordinator in data["coordinators"].values():
            coordinator.async_unload()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
