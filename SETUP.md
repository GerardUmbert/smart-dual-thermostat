# Setup walkthrough

This documents every field of the config flow, in the exact order Home
Assistant presents them, with the underlying key name and what it
controls. It exists so an agent guiding a user through the UI (or a user
following along) always has the exact field to look for, instead of
guessing from the on-screen label alone.

There is no generic "write this config entry" API — Smart Dual Thermostat
is a config-flow integration, not YAML. It cannot be installed by writing
a file or calling a generic helper/automation-setter tool the way
`configuration.yaml` or `automations.yaml` can. Setup only happens by
submitting the flow's forms, one step at a time, through Settings ->
Devices & services -> Add integration -> "Smart Dual Thermostat" in the
HA UI (or, if a client has one, through HA's Config Flow REST/WS API,
which follows the same step sequence below).

## Step 1 — hub (`async_step_user`)

House-wide defaults, shared by every zone unless a zone overrides them.

| Field (key) | Type | Required | Notes |
|---|---|---|---|
| Default outdoor temperature sensor (`outdoor_sensor`) | entity (`sensor` or `weather`) | No | Falls back to nothing if omitted — zones without their own override then get no outdoor reading, which disables season-override behavior and shoulder-season temperature decisions for them. |
| Season detection (`season_mode`) | select: `hemisphere` \| `custom_months` \| `temp_only` | No, default `hemisphere` | `hemisphere` derives cool/heat months from HA's own configured latitude (Settings -> General -> Location) — nothing else to set. `custom_months` requires filling the two month fields below. `temp_only` ignores season entirely. |
| Notification service (`notify_service`) | entity (`notify` domain) | No | Not yet wired to any behavior in the coordinator — reserved for future away-mode/external-change notifications. |
| Away mode entity (`away_entity`) | entity (`input_boolean` or `binary_sensor`) | No | Same — reserved, not yet consumed. |
| Custom cooling months (`months_cool`) | multi-select 1-12 | Only used if `season_mode = custom_months` | Shown regardless of season_mode selection; ignored otherwise. |
| Custom heating months (`months_heat`) | multi-select 1-12 | Only used if `season_mode = custom_months` | Same. |
| Cooling season cold-snap override (`cool_season_heat_override_below`) | float, °C | No, default `15.0` | During a cooling-default month, force heat instead if outdoor temp drops below this. |
| Heating season heat-wave override (`heat_season_cool_override_above`) | float, °C | No, default `26.0` | During a heating-default month, force cool instead if outdoor temp rises above this. |
| Shoulder-season cool threshold (`neutral_cool_above`) | float, °C | No, default `22.0` | Used only in months with no seasonal default (or in `temp_only` mode): cool if outdoor temp is above this. |
| Shoulder-season heat threshold (`neutral_heat_below`) | float, °C | No, default `18.0` | Same: heat if outdoor temp is below this. |

Defaults are tuned for a temperate/Mediterranean climate. Installs
elsewhere should adjust the four threshold values to their own climate —
see the main README's "Why not generic_thermostat" section for why these
aren't derived automatically from location.

## Step 2 — zone (`async_step_zone`, repeats)

One zone pairs a heat actuator with a cool actuator. Submit this form
once per zone (whole house = one zone; per-floor = one zone per floor).

| Field (key) | Type | Required | Notes |
|---|---|---|---|
| Zone name (`name`) | text | Yes | e.g. "Casa", "Planta baja", "Dormitorios". |
| Heating actuator (`heat_entity`) | entity (`climate` or `switch`) | No* | *At least one of heat/cool entity is required — the form rejects submission with error `zone_needs_actuator` if both are blank. |
| Heating actuator scale correction (`heat_scale`) | float | No, default `1.0` | Linear correction: `real_temp = device_temp * scale + offset`. Set to `5` for a Tuya-style thermostat with the known ÷5 scale bug (real_temp = device_temp × 5). |
| Heating actuator offset correction (`heat_offset`) | float | No, default `0.0` | Applied after scale. |
| Cooling actuator (`cool_entity`) | entity (`climate` or `switch`) | No* | See above. |
| Cooling actuator scale correction (`cool_scale`) | float | No, default `1.0` | Same mechanism as heat. |
| Cooling actuator offset correction (`cool_offset`) | float | No, default `0.0` | |
| Supporting fans (`cool_fan_entities`) | entity list (`fan` domain, multi) | No | Turned on/off alongside the cooling actuator. |
| Indoor temperature sensor (`indoor_sensor`) | entity (`sensor`, temperature device class) | No | Used for both `current_temperature` display and heat-mode relax detection. Falls back to the cool actuator's own reported `current_temperature` if omitted. |
| Outdoor sensor override (`outdoor_sensor_override`) | entity (`sensor` or `weather`) | No | Falls back to the hub-level `outdoor_sensor` if omitted. |
| Dial increment (`temp_step`) | select: `0.5` \| `1.0` | No, default derived from HA's system temperature unit (`0.5` for °C, `1.0` for °F) | Set to `1.0` even on a °C system if the actuator only accepts whole-degree steps. |
| Cool: minimum settable (`cool_min`) | float, °C | No, default `22.0` | |
| Cool: relaxed maintenance point (`cool_relaxed`) | float, °C | No, default `25.0` | Must be greater than `cool_min` for relax-on-reached to ever trigger. |
| Cool: maximum ceiling (`cool_max`) | float, °C | No, default `27.0` | |
| Heat: minimum settable (`heat_min`) | float, °C | No, default `18.0` | |
| Heat: relaxed maintenance point (`heat_relaxed`) | float, °C | No, default `21.0` | Must be less than `heat_max` for relax-on-reached to ever trigger. |
| Heat: maximum ceiling (`heat_max`) | float, °C | No, default `24.0` | |

After submitting, the flow moves to "add another zone?" — answer yes to
repeat this step for another zone, or no to finish and create the entry.

## Reconfiguring after setup

Settings -> Devices & services -> Smart Dual Thermostat -> Configure
opens the options flow: edit any hub-level field (step 1's table above),
then "Manage zones" lets you add a new zone or pick an existing one by
name to re-open exactly the zone form above, pre-filled with its current
values. There's no separate "edit" schema — reconfiguring a zone reuses
the same field table as creating one.

## Worked example — a Tuya heater + mini-split AC, single zone

Matches the kind of single-house, two-device setup this project
generalizes from:

- Hub: `outdoor_sensor` = your local `weather.*` entity, `season_mode` =
  `hemisphere` (auto-detects from your HA instance's own location),
  everything else default.
- Zone: `name` = "Casa", `heat_entity` = your Tuya thermostat's `climate.*`
  entity with `heat_scale` = `5`, `cool_entity` = your AC's `climate.*`
  entity (`cool_scale` left at `1.0`), `cool_fan_entities` = the
  supporting fan, ranges left at the defaults (22/25/27 cool, 18/21/24
  heat) or adjusted to taste, `temp_step` = `0.5`.
- Finish without adding another zone.

Result: a single `climate.casa` entity, plus `select.casa_mode` and six
`number.casa_*` range entities.

## What's genuinely not agent-settable today

- **No config-flow REST/WS driver documented here or tested against any
  MCP server.** This file only documents the fields; it does not claim
  any particular MCP tool can submit them. If your HA MCP server exposes
  a generic config-flow tool, use the field tables above as its script;
  if it only exposes YAML/helper/automation setters (the common case),
  it cannot install this integration — a human has to click through
  Settings -> Devices & services at least once.
- **`notify_service` and `away_entity`** are captured in the hub schema
  but not yet consumed by any coordinator behavior — see the main
  README's project status.
