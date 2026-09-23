"""Constants and config-entry data shape for Smart Dual Thermostat."""
from __future__ import annotations

DOMAIN = "smart_dual_thermostat"

PLATFORMS = ["climate", "select", "number"]

# ---------------------------------------------------------------------------
# Config entry data keys (hub level)
# ---------------------------------------------------------------------------
CONF_ZONES = "zones"
CONF_OUTDOOR_SENSOR = "outdoor_sensor"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_AWAY_ENTITY = "away_entity"
CONF_SEASON_MODE = "season_mode"

# season_mode values
SEASON_MODE_HEMISPHERE = "hemisphere"      # derive from HA's configured latitude
SEASON_MODE_CUSTOM_MONTHS = "custom_months"  # user-supplied month table
SEASON_MODE_TEMP_ONLY = "temp_only"        # ignore season entirely, decide purely from outdoor temp

DEFAULT_SEASON_MODE = SEASON_MODE_HEMISPHERE

# ---------------------------------------------------------------------------
# Per-zone keys (each entry in CONF_ZONES is a dict shaped like this)
# ---------------------------------------------------------------------------
CONF_ZONE_ID = "zone_id"          # stable slug, generated at creation
CONF_ZONE_NAME = "name"

CONF_HEAT_ENTITY = "heat_entity"          # climate.* or switch.* actuator
CONF_HEAT_ENTITY_DOMAIN = "heat_entity_domain"  # "climate" | "switch" | "number"
CONF_HEAT_HVAC_MODE = "heat_hvac_mode"    # hvac_mode string to send when this actuator means "on" (climate actuators only)
CONF_HEAT_SCALE = "heat_scale"            # linear correction: real_temp = device_temp * scale + offset
CONF_HEAT_OFFSET = "heat_offset"

CONF_COOL_ENTITY = "cool_entity"
CONF_COOL_ENTITY_DOMAIN = "cool_entity_domain"
CONF_COOL_HVAC_MODE = "cool_hvac_mode"
CONF_COOL_SCALE = "cool_scale"
CONF_COOL_OFFSET = "cool_offset"

CONF_COOL_FAN_ENTITIES = "cool_fan_entities"  # list of fan.* to turn on/off alongside cooling

# A single classic dual-circuit thermostat — one physical unit with its own
# manual heat/cool switch routing one relay to either circuit, plus its own
# temperature sensor (e.g. an old-style wall thermostat, or its smart
# replacement that still has real heat/cool hvac_modes rather than being
# mode-agnostic like CONF_ZONE_DISPLAY_ENTITY). Mutually exclusive with
# CONF_HEAT_ENTITY/CONF_COOL_ENTITY — a zone uses either two separate
# actuators, or one combined actuator, never both. Unlike the display
# entity, this DOES drive real HVAC hardware and its reported hvac_mode is
# trusted as genuine heat/cool intent when changed externally, since the
# device can express that unambiguously (it has a real physical switch).
CONF_ZONE_COMBINED_ENTITY = "combined_entity"
CONF_COMBINED_SCALE = "combined_scale"
CONF_COMBINED_OFFSET = "combined_offset"

CONF_ZONE_OUTDOOR_SENSOR_OVERRIDE = "outdoor_sensor_override"  # falls back to hub-level CONF_OUTDOOR_SENSOR
CONF_ZONE_INDOOR_SENSOR = "indoor_sensor"  # optional dedicated indoor temp sensor for relax detection

# Optional third, mode-agnostic climate entity for this zone — e.g. a bare
# Zigbee/WiFi thermostat wired to nothing, used purely as a physical dial.
# Two-way synced with the zone's own desired/target, but never used to
# decide or force heat/cool mode (unlike heat_entity/cool_entity) and never
# itself commanded to actuate anything. Its own hvac_mode is always pinned
# to HVACMode.AUTO so its mode selector can't be touched into forcing a
# mode by mistake.
CONF_ZONE_DISPLAY_ENTITY = "display_entity"

CONF_ZONE_TEMP_STEP = "temp_step"  # target temperature increment for this zone's dial
# Temperature UNIT is not configurable per zone or per hub — it always
# follows Home Assistant's own system-wide unit (hass.config.units), same
# as every other climate integration. Only the STEP (increment) is
# configurable, since some actuators only support whole-degree steps.
DEFAULT_TEMP_STEP_CELSIUS = 0.5
DEFAULT_TEMP_STEP_FAHRENHEIT = 1.0

# comfort range, per mode (6 values total, mirrors termostato_virtual's 6 input_numbers)
CONF_COOL_MIN = "cool_min"
CONF_COOL_RELAXED = "cool_relaxed"
CONF_COOL_MAX = "cool_max"
CONF_HEAT_MIN = "heat_min"
CONF_HEAT_RELAXED = "heat_relaxed"
CONF_HEAT_MAX = "heat_max"

DEFAULT_COOL_MIN = 22.0
DEFAULT_COOL_RELAXED = 25.0
DEFAULT_COOL_MAX = 27.0
DEFAULT_HEAT_MIN = 18.0
DEFAULT_HEAT_RELAXED = 21.0
DEFAULT_HEAT_MAX = 24.0

DEFAULT_HEAT_HVAC_MODE = "heat"
DEFAULT_COOL_HVAC_MODE = "cool"

# custom month table (only used when season_mode == custom_months)
CONF_MONTHS_COOL = "months_cool"
CONF_MONTHS_HEAT = "months_heat"
# outdoor-temp exception thresholds that can override the seasonal default
CONF_COOL_SEASON_HEAT_OVERRIDE_BELOW = "cool_season_heat_override_below"  # e.g. 15
CONF_HEAT_SEASON_COOL_OVERRIDE_ABOVE = "heat_season_cool_override_above"  # e.g. 26
# shoulder-season (no default) thresholds
CONF_NEUTRAL_COOL_ABOVE = "neutral_cool_above"  # e.g. 22
CONF_NEUTRAL_HEAT_BELOW = "neutral_heat_below"  # e.g. 18

DEFAULT_COOL_SEASON_HEAT_OVERRIDE_BELOW = 15.0
DEFAULT_HEAT_SEASON_COOL_OVERRIDE_ABOVE = 26.0
DEFAULT_NEUTRAL_COOL_ABOVE = 22.0
DEFAULT_NEUTRAL_HEAT_BELOW = 18.0

# ---------------------------------------------------------------------------
# Runtime / derived entity naming
# ---------------------------------------------------------------------------
FORCED_MODE_AUTO = "auto"
FORCED_MODE_HEAT = "heat"
FORCED_MODE_COOL = "cool"
FORCED_MODE_OPTIONS = [FORCED_MODE_AUTO, FORCED_MODE_HEAT, FORCED_MODE_COOL]

DECIDED_MODE_HEAT = "heat"
DECIDED_MODE_COOL = "cool"
DECIDED_MODE_NEUTRAL = "neutral"

RECHECK_INTERVAL_MINUTES = 20

ATTR_ZONE_ID = "zone_id"
