# Smart Dual Thermostat

A Home Assistant integration for houses that heat and cool through two
separate systems (e.g. central heating + a mini-split AC) instead of one
device that does both. One dial per zone decides automatically whether to
heat or cool, based on season and outdoor temperature, so you don't have
to think about which device to turn on.

Supports any number of **zones** — typically one for the whole house, but
also one per floor, or any other split where a heating actuator and a
cooling actuator should be controlled together as a pair.

## Why not `generic_thermostat` or `dual_smart_thermostat`?

Those assume a single heater/cooler pair driven from a single sensor with
manual mode selection. This integration adds:

- **Automatic heat/cool decision** per zone, from season + live outdoor
  temperature, with a per-zone manual override (auto/heat/cool).
- **Safe comfort ranges** (min / relaxed / max per mode) that clamp
  whatever target you set, and auto-relax the target once it's reached
  (efficiency in cooling, a safety ceiling in heating).
- **External-change sync**: if either actuator is changed by voice, its
  own app, or a physical remote, the zone picks up the change and forces
  its mode instead of fighting it on the next re-evaluation.
- **Per-actuator scale/offset correction**, for devices that don't report
  temperature in real degrees C (a known quirk on some Tuya-based
  thermostats).
- **Multiple independent zones** in one config entry, each pairing its
  own heat/cool actuators.

## Installation

### HACS (custom repository)

1. HACS -> Integrations -> ⋮ -> Custom repositories.
2. Add this repository URL, category "Integration".
3. Install "Smart Dual Thermostat", restart Home Assistant.

### Manual

Copy `custom_components/smart_dual_thermostat/` into your HA
`config/custom_components/` folder and restart.

## Setup

Settings -> Devices & services -> Add integration -> "Smart Dual
Thermostat".

1. **Hub step**: default outdoor sensor (a `sensor` or `weather` entity),
   season detection strategy, optional notification service, optional
   away-mode entity.
2. **Zone step** (repeats for as many zones as you need): name the zone,
   pick its heating actuator and/or cooling actuator (`climate` or
   `switch` entities), optional supporting fans, optional dedicated
   indoor sensor, and the six comfort-range values (min/relaxed/max for
   each mode). Leave heat or cool blank for a zone that only does one.
3. Repeat step 2 for additional zones (e.g. one per floor), or finish.

Each zone becomes a normal `climate.*` entity — usable with HA's built-in
thermostat card, voice assistants, and scripts with no custom card
required. `HVAC_MODE_AUTO` is the automatic heat/cool decision; `HEAT` /
`COOL` force that mode; `OFF` is the panic-button shutdown (forces both
actuators off).

A `select.*_mode` and six `number.*` comfort-range entities are also
created per zone for dashboards that want direct access to the forced
mode and range editing without going back into the integration options.

### Season detection

- **Automatic (hemisphere)**: derives Northern/Southern season months
  from your Home Assistant instance's configured location. No
  configuration needed for most installations.
- **Custom month table**: define your own cool/heat months, for climates
  that don't follow the typical hemisphere pattern.
- **Outdoor temperature only**: skip season weighting entirely and decide
  purely from live outdoor temperature thresholds.

In all three modes, an unusually cold day during the cooling season (or
an unusually hot day during the heating season) can still override the
seasonal default.

### Actuator scale/offset correction

If your heating or cooling device doesn't accept/report real degrees C
(some Tuya devices apply a fixed division), set the scale/offset fields
when pairing that actuator in the zone step. Defaults to no correction
(scale 1, offset 0) for ordinary devices.

## Project origin

This generalizes a house-specific "termostato virtual" built from a bundle
of Home Assistant YAML automations into a reusable, multi-zone Python
integration with a proper config flow — no YAML editing required to
install or reconfigure.

## License

MIT — see `LICENSE`.
