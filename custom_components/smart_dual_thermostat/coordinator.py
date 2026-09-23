"""Per-zone decision + actuation coordinator.

Generalizes automation_termostato_virtual_decidir.yaml and
automation_termostato_virtual_relajar.yaml from the original single-house
project into a reusable, multi-zone Python coordinator:

- One ZoneCoordinator per configured zone, holding its own dial, forced
  mode, comfort ranges, and paired heat/cool actuators.
- decide-and-act: clamps the dial to the active mode's safe range, sends
  hvac_mode before any set_temperature (actuators ignore temperature
  changes while off), and writes the clamped value back to the dial.
- relax-on-reached: once the real temperature reaches the requested
  target, relaxes the setpoint to the configured maintenance point,
  without exceeding the safe range and without repeating once already
  relaxed.
- voice/external sync: if the paired actuator is changed by some other
  means (its own app, a physical remote, another automation), the zone
  picks up the new value and forces its mode, the same way the original
  sync_desde_aire / sync_desde_calefaccion automations did.

Physical writes go through Correction (quirks.py) so device-specific
scale/offset bugs never leak into this logic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    DECIDED_MODE_COOL,
    DECIDED_MODE_HEAT,
    DECIDED_MODE_NEUTRAL,
    FORCED_MODE_AUTO,
    FORCED_MODE_COOL,
    FORCED_MODE_HEAT,
    RECHECK_INTERVAL_MINUTES,
)
from .quirks import Correction
from .season import decide_mode

_LOGGER = logging.getLogger(__name__)


@dataclass
class ComfortRange:
    cool_min: float
    cool_relaxed: float
    cool_max: float
    heat_min: float
    heat_relaxed: float
    heat_max: float

    def clamp(self, mode: str, value: float) -> float:
        if mode == DECIDED_MODE_COOL:
            return max(min(value, self.cool_max), self.cool_min)
        if mode == DECIDED_MODE_HEAT:
            return max(min(value, self.heat_max), self.heat_min)
        return value


@dataclass
class ActuatorConfig:
    entity_id: str | None
    entity_domain: str = "climate"
    hvac_mode: str = "heat"
    correction: Correction = field(default_factory=Correction)


@dataclass
class ZoneConfig:
    zone_id: str
    name: str
    heat: ActuatorConfig
    cool: ActuatorConfig
    cool_fan_entities: list[str]
    comfort: ComfortRange
    indoor_sensor: str | None
    outdoor_sensor: str | None
    temp_step: float = 0.5
    # Optional third, mode-agnostic climate entity (e.g. a bare Zigbee/WiFi
    # thermostat wired to nothing) used purely as a physical dial. Two-way
    # synced with desired/target but never forces heat/cool mode and is
    # never itself commanded to actuate anything — see const.py.
    display_entity: str | None = None
    # A single classic dual-circuit thermostat (its own manual heat/cool
    # switch, one relay, one real device) — mutually exclusive with
    # heat/cool above; when set, heat.entity_id and cool.entity_id are
    # expected to be None and this is used instead. See const.py.
    combined: ActuatorConfig | None = None


class ZoneCoordinator:
    """Owns the runtime state and behavior for a single zone."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: ZoneConfig,
        *,
        active: bool = False,
        desired: float = 21.0,
        forced_mode: str = FORCED_MODE_AUTO,
        default_outdoor_sensor: str | None = None,
        season_mode: str,
        custom_cool_months: list[int] | None,
        custom_heat_months: list[int] | None,
        cool_season_heat_override_below: float,
        heat_season_cool_override_above: float,
        neutral_cool_above: float,
        neutral_heat_below: float,
    ) -> None:
        self.hass = hass
        self.config = config
        self.active = active
        self.desired = desired
        self.forced_mode = forced_mode
        self._default_outdoor_sensor = default_outdoor_sensor
        self._season_mode = season_mode
        self._custom_cool_months = custom_cool_months
        self._custom_heat_months = custom_heat_months
        self._cool_season_heat_override_below = cool_season_heat_override_below
        self._heat_season_cool_override_above = heat_season_cool_override_above
        self._neutral_cool_above = neutral_cool_above
        self._neutral_heat_below = neutral_heat_below
        self._unsubs: list[callable] = []
        self._relaxed = False
        self.on_update: list[callable] = []

    # -- lifecycle ---------------------------------------------------

    def async_setup(self) -> None:
        entities_to_watch = [
            e
            for e in (self.config.heat.entity_id, self.config.cool.entity_id)
            if e
        ]
        if entities_to_watch:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, entities_to_watch, self._handle_actuator_changed
                )
            )
        if self.config.combined and self.config.combined.entity_id:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass,
                    [self.config.combined.entity_id],
                    self._handle_combined_changed,
                )
            )
        if self.config.display_entity:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, [self.config.display_entity], self._handle_display_changed
                )
            )
        if self.config.indoor_sensor:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, [self.config.indoor_sensor], self._handle_relax_check
                )
            )
        self._unsubs.append(
            async_track_time_interval(
                self.hass,
                self._handle_periodic_recheck,
                timedelta(minutes=RECHECK_INTERVAL_MINUTES),
            )
        )

    def async_unload(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    def _notify_listeners(self) -> None:
        for cb in self.on_update:
            cb()
        if self.config.display_entity:
            self.hass.async_create_task(self._async_sync_display())

    # -- outdoor temp / mode decision ---------------------------------

    def _outdoor_temp(self) -> float | None:
        sensor = self.config.outdoor_sensor or self._default_outdoor_sensor
        if not sensor:
            return None
        state = self.hass.states.get(sensor)
        if state is None:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            try:
                return float(state.attributes.get("temperature"))
            except (TypeError, ValueError):
                return None

    def _effective_mode(self) -> str:
        if self.forced_mode in (FORCED_MODE_HEAT, FORCED_MODE_COOL):
            return self.forced_mode
        latitude = self.hass.config.latitude
        return decide_mode(
            season_mode=self._season_mode,
            now=dt_util.now(),
            latitude=latitude,
            custom_cool_months=self._custom_cool_months,
            custom_heat_months=self._custom_heat_months,
            outdoor_temp=self._outdoor_temp(),
            cool_season_heat_override_below=self._cool_season_heat_override_below,
            heat_season_cool_override_above=self._heat_season_cool_override_above,
            neutral_cool_above=self._neutral_cool_above,
            neutral_heat_below=self._neutral_heat_below,
        )

    # -- public actions ------------------------------------------------

    async def async_set_desired(self, value: float) -> None:
        self.desired = value
        if not self.active:
            self.active = True
        self._relaxed = False
        await self.async_decide_and_act()

    async def async_set_forced_mode(self, mode: str) -> None:
        self.forced_mode = mode
        await self.async_decide_and_act()

    async def async_turn_off(self) -> None:
        """Panic-button behavior: force all actuators off, reset forced mode."""
        self.active = False
        self.forced_mode = FORCED_MODE_AUTO
        if self.config.heat.entity_id:
            await self._async_set_hvac_mode(self.config.heat, "off")
        if self.config.cool.entity_id:
            await self._async_set_hvac_mode(self.config.cool, "off")
        if self.config.combined and self.config.combined.entity_id:
            await self._async_set_hvac_mode(self.config.combined, "off")
        for fan_entity in self.config.cool_fan_entities:
            await self.hass.services.async_call(
                "fan", "turn_off", {"entity_id": fan_entity}, blocking=False
            )
        self._notify_listeners()

    async def async_decide_and_act(self) -> None:
        if not self.active:
            return
        mode = self._effective_mode()
        clamped = self.config.comfort.clamp(mode, self.desired)

        if self.config.combined and self.config.combined.entity_id:
            # One device, its own relay switches circuits — just tell it
            # which mode to be in. No second entity to turn off.
            if mode == DECIDED_MODE_HEAT:
                await self._async_set_hvac_mode(self.config.combined, "heat")
                await self._async_set_temperature(self.config.combined, clamped)
                for fan_entity in self.config.cool_fan_entities:
                    await self.hass.services.async_call(
                        "fan", "turn_off", {"entity_id": fan_entity}, blocking=False
                    )
            elif mode == DECIDED_MODE_COOL:
                await self._async_set_hvac_mode(self.config.combined, "cool")
                await self._async_set_temperature(self.config.combined, clamped)
                for fan_entity in self.config.cool_fan_entities:
                    await self.hass.services.async_call(
                        "fan", "turn_on", {"entity_id": fan_entity}, blocking=False
                    )
            # DECIDED_MODE_NEUTRAL: leave the device untouched.
        elif mode == DECIDED_MODE_HEAT and self.config.heat.entity_id:
            await self._async_set_hvac_mode(self.config.heat, self.config.heat.hvac_mode)
            await self._async_set_temperature(self.config.heat, clamped)
            if self.config.cool.entity_id:
                await self._async_set_hvac_mode(self.config.cool, "off")
            for fan_entity in self.config.cool_fan_entities:
                await self.hass.services.async_call(
                    "fan", "turn_off", {"entity_id": fan_entity}, blocking=False
                )
        elif mode == DECIDED_MODE_COOL and self.config.cool.entity_id:
            await self._async_set_hvac_mode(self.config.cool, self.config.cool.hvac_mode)
            await self._async_set_temperature(self.config.cool, clamped)
            for fan_entity in self.config.cool_fan_entities:
                await self.hass.services.async_call(
                    "fan", "turn_on", {"entity_id": fan_entity}, blocking=False
                )
        # DECIDED_MODE_NEUTRAL: leave actuators untouched.

        if clamped != self.desired:
            self.desired = clamped
        self._relaxed = False
        self._notify_listeners()

    # -- relax-on-reached ------------------------------------------------

    async def _handle_relax_check(self, event) -> None:  # noqa: ANN001 - HA event
        await self.async_check_relax()

    async def async_check_relax(self) -> None:
        if not self.active or self._relaxed:
            return
        mode = self._effective_mode()
        comfort = self.config.comfort
        combined = self.config.combined if self.config.combined and self.config.combined.entity_id else None
        cool_actuator = combined or self.config.cool
        heat_actuator = combined or self.config.heat

        if mode == DECIDED_MODE_COOL and cool_actuator.entity_id:
            current = self._actuator_current_temperature(cool_actuator)
            target = self._actuator_target_temperature(cool_actuator)
            if (
                current is not None
                and target is not None
                and current <= self.desired
                and comfort.cool_relaxed > self.desired
                and abs(target - self.desired) < 0.1
            ):
                await self._async_set_hvac_mode(cool_actuator, "cool")
                await self._async_set_temperature(cool_actuator, comfort.cool_relaxed)
                self._relaxed = True
                self._notify_listeners()
        elif mode == DECIDED_MODE_HEAT and heat_actuator.entity_id:
            indoor = self._indoor_temperature()
            target = self._actuator_target_temperature(heat_actuator)
            if (
                indoor is not None
                and target is not None
                and indoor >= self.desired
                and comfort.heat_relaxed < self.desired
                and abs(target - self.desired) < 0.1
            ):
                await self._async_set_hvac_mode(heat_actuator, "heat")
                await self._async_set_temperature(heat_actuator, comfort.heat_relaxed)
                self._relaxed = True
                self._notify_listeners()

    def _indoor_temperature(self) -> float | None:
        if self.config.indoor_sensor:
            state = self.hass.states.get(self.config.indoor_sensor)
            if state is not None:
                try:
                    return float(state.state)
                except (TypeError, ValueError):
                    return None
        if self.config.combined and self.config.combined.entity_id:
            return self._actuator_current_temperature(self.config.combined)
        return self._actuator_current_temperature(self.config.cool)

    # -- external / voice sync ------------------------------------------

    async def _handle_actuator_changed(self, event) -> None:  # noqa: ANN001 - HA event
        entity_id = event.data.get("entity_id")
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return

        if entity_id == self.config.heat.entity_id:
            actuator, forced_mode, comfort_min, comfort_max = (
                self.config.heat,
                FORCED_MODE_HEAT,
                self.config.comfort.heat_min,
                self.config.comfort.heat_max,
            )
        elif entity_id == self.config.cool.entity_id:
            actuator, forced_mode, comfort_min, comfort_max = (
                self.config.cool,
                FORCED_MODE_COOL,
                self.config.comfort.cool_min,
                self.config.comfort.cool_max,
            )
        else:
            return

        raw_temp = new_state.attributes.get("temperature")
        if raw_temp is None:
            return
        try:
            real_temp = actuator.correction.to_real(float(raw_temp))
        except (TypeError, ValueError):
            return

        clamped = max(min(real_temp, comfort_max), comfort_min)

        was_off = not self.active
        self.active = True
        self.forced_mode = forced_mode
        self.desired = clamped
        self._relaxed = False
        _LOGGER.debug(
            "Zone %s: external change on %s -> desired=%.1f forced=%s (was_off=%s)",
            self.config.zone_id,
            entity_id,
            clamped,
            forced_mode,
            was_off,
        )
        # Act immediately rather than waiting for the next periodic
        # recheck (up to RECHECK_INTERVAL_MINUTES later) — e.g. touching
        # the heat actuator while the zone was cooling should turn the AC
        # off right away, not up to 20 minutes later.
        await self.async_decide_and_act()

    async def _handle_combined_changed(self, event) -> None:  # noqa: ANN001 - HA event
        """Sync from a single dual-circuit thermostat.

        Unlike the display entity, this device genuinely drives hardware
        and can express heat/cool intent unambiguously via its own
        reported hvac_mode (its manual switch already picked a real
        circuit) — so, unlike heat_entity/cool_entity sync, mode is read
        from the device's actual state rather than assumed from which
        config field it's paired under.
        """
        new_state: State | None = event.data.get("new_state")
        if new_state is None or not self.config.combined:
            return

        reported_mode = new_state.state
        if reported_mode == "heat":
            forced_mode, comfort_min, comfort_max = (
                FORCED_MODE_HEAT,
                self.config.comfort.heat_min,
                self.config.comfort.heat_max,
            )
        elif reported_mode == "cool":
            forced_mode, comfort_min, comfort_max = (
                FORCED_MODE_COOL,
                self.config.comfort.cool_min,
                self.config.comfort.cool_max,
            )
        else:
            # off, or a mode this integration doesn't model (e.g. fan_only,
            # dry) — nothing to sync.
            return

        raw_temp = new_state.attributes.get("temperature")
        if raw_temp is None:
            return
        try:
            real_temp = self.config.combined.correction.to_real(float(raw_temp))
        except (TypeError, ValueError):
            return

        clamped = max(min(real_temp, comfort_max), comfort_min)

        was_off = not self.active
        self.active = True
        self.forced_mode = forced_mode
        self.desired = clamped
        self._relaxed = False
        _LOGGER.debug(
            "Zone %s: combined actuator changed -> mode=%s desired=%.1f (was_off=%s)",
            self.config.zone_id,
            forced_mode,
            clamped,
            was_off,
        )
        await self.async_decide_and_act()

    async def _handle_display_changed(self, event) -> None:  # noqa: ANN001 - HA event
        """Sync from the mode-agnostic display thermostat.

        Unlike _handle_actuator_changed, this never sets forced_mode —
        the whole point of the display entity is that it can't express
        heat/cool intent, only a target temperature. Mode stays whatever
        the zone would otherwise decide (auto season/outdoor logic, or a
        forced mode set some other way, e.g. the select entity or the
        zone's own climate entity).
        """
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            return
        raw_temp = new_state.attributes.get("temperature")
        if raw_temp is None:
            return
        try:
            value = float(raw_temp)
        except (TypeError, ValueError):
            return
        # Guards against _async_sync_display's own writes echoing back as
        # a state-changed event and re-triggering this handler in a loop.
        if self.active and abs(value - self.desired) < 0.01:
            return
        # async_set_desired() already activates the zone if needed, clears
        # the relax flag, and calls async_decide_and_act() immediately.
        await self.async_set_desired(value)

    async def _async_sync_display(self) -> None:
        """Mirror this zone's current target onto the display entity.

        Mode is always pinned to AUTO on the display device itself — it
        has no business reflecting heat/cool, and pinning it avoids its
        own mode selector being touched into accidentally forcing one.
        """
        if not self.config.display_entity:
            return
        await self.hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": self.config.display_entity, "hvac_mode": "auto" if self.active else "off"},
            blocking=False,
        )
        if self.active:
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": self.config.display_entity, "temperature": self.desired},
                blocking=False,
            )

    async def _handle_periodic_recheck(self, now: datetime) -> None:  # noqa: ANN001
        await self.async_decide_and_act()

    # -- actuator IO helpers ----------------------------------------------

    async def _async_set_hvac_mode(self, actuator: ActuatorConfig, hvac_mode: str) -> None:
        if not actuator.entity_id:
            return
        if actuator.entity_domain != "climate":
            service = "turn_on" if hvac_mode != "off" else "turn_off"
            await self.hass.services.async_call(
                actuator.entity_domain, service, {"entity_id": actuator.entity_id}, blocking=False
            )
            return
        await self.hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": actuator.entity_id, "hvac_mode": hvac_mode},
            blocking=False,
        )

    async def _async_set_temperature(self, actuator: ActuatorConfig, real_value: float) -> None:
        if not actuator.entity_id:
            return
        device_value = actuator.correction.to_device(real_value)
        if actuator.entity_domain == "climate":
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": actuator.entity_id, "temperature": device_value},
                blocking=False,
            )
        elif actuator.entity_domain == "number":
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": actuator.entity_id, "value": device_value},
                blocking=False,
            )
        # switch-domain actuators have no temperature to set.

    def _actuator_current_temperature(self, actuator: ActuatorConfig) -> float | None:
        if not actuator.entity_id:
            return None
        state = self.hass.states.get(actuator.entity_id)
        if state is None:
            return None
        raw = state.attributes.get("current_temperature")
        if raw is None:
            return None
        try:
            return actuator.correction.to_real(float(raw))
        except (TypeError, ValueError):
            return None

    def _actuator_target_temperature(self, actuator: ActuatorConfig) -> float | None:
        if not actuator.entity_id:
            return None
        state = self.hass.states.get(actuator.entity_id)
        if state is None:
            return None
        raw = state.attributes.get("temperature")
        if raw is None:
            return None
        try:
            return actuator.correction.to_real(float(raw))
        except (TypeError, ValueError):
            return None
