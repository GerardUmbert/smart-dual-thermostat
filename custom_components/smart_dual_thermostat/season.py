"""Season/mode decision logic.

Generalizes the month + outdoor-temperature heuristic from the original
single-house implementation into three pluggable strategies:

- hemisphere: derive the default season from HA's configured latitude
  (Northern vs Southern) instead of hardcoding specific months.
- custom_months: user supplies their own cool/heat month lists (for
  installations with unusual local climate patterns).
- temp_only: skip season weighting entirely, decide purely from live
  outdoor temperature thresholds.

In all three modes, an out-of-season outdoor temperature can still
override the seasonal default (e.g. an unseasonably cold day in what is
normally the cooling season forces heat instead).
"""
from __future__ import annotations

from datetime import datetime

from .const import (
    DECIDED_MODE_COOL,
    DECIDED_MODE_HEAT,
    DECIDED_MODE_NEUTRAL,
    SEASON_MODE_CUSTOM_MONTHS,
    SEASON_MODE_HEMISPHERE,
    SEASON_MODE_TEMP_ONLY,
)

NORTHERN_HEMISPHERE_COOL_MONTHS = [6, 7, 8, 9]
NORTHERN_HEMISPHERE_HEAT_MONTHS = [11, 12, 1, 2, 3]
SOUTHERN_HEMISPHERE_COOL_MONTHS = [12, 1, 2, 3]
SOUTHERN_HEMISPHERE_HEAT_MONTHS = [6, 7, 8, 9]


def _seasonal_default(
    month: int, cool_months: list[int], heat_months: list[int]
) -> str:
    if month in cool_months:
        return DECIDED_MODE_COOL
    if month in heat_months:
        return DECIDED_MODE_HEAT
    return DECIDED_MODE_NEUTRAL


def decide_mode(
    *,
    season_mode: str,
    now: datetime,
    latitude: float | None,
    custom_cool_months: list[int] | None,
    custom_heat_months: list[int] | None,
    outdoor_temp: float | None,
    cool_season_heat_override_below: float,
    heat_season_cool_override_above: float,
    neutral_cool_above: float,
    neutral_heat_below: float,
) -> str:
    """Return DECIDED_MODE_HEAT / _COOL / _NEUTRAL.

    Mirrors the original decision table: a seasonal default that can be
    overridden by an atypical outdoor temperature, falling back to
    pure-temperature thresholds when there is no seasonal default
    (shoulder months, or temp_only mode).
    """
    if season_mode == SEASON_MODE_TEMP_ONLY:
        seasonal_default = DECIDED_MODE_NEUTRAL
    elif season_mode == SEASON_MODE_CUSTOM_MONTHS:
        seasonal_default = _seasonal_default(
            now.month, custom_cool_months or [], custom_heat_months or []
        )
    else:  # SEASON_MODE_HEMISPHERE
        southern = (latitude or 0) < 0
        cool_months = (
            SOUTHERN_HEMISPHERE_COOL_MONTHS
            if southern
            else NORTHERN_HEMISPHERE_COOL_MONTHS
        )
        heat_months = (
            SOUTHERN_HEMISPHERE_HEAT_MONTHS
            if southern
            else NORTHERN_HEMISPHERE_HEAT_MONTHS
        )
        seasonal_default = _seasonal_default(now.month, cool_months, heat_months)

    if outdoor_temp is None:
        return seasonal_default

    if seasonal_default == DECIDED_MODE_COOL and outdoor_temp < cool_season_heat_override_below:
        return DECIDED_MODE_HEAT
    if seasonal_default == DECIDED_MODE_HEAT and outdoor_temp > heat_season_cool_override_above:
        return DECIDED_MODE_COOL
    if seasonal_default in (DECIDED_MODE_COOL, DECIDED_MODE_HEAT):
        return seasonal_default

    # No seasonal default (shoulder season / temp_only) -> decide purely by
    # outdoor temperature.
    if outdoor_temp > neutral_cool_above:
        return DECIDED_MODE_COOL
    if outdoor_temp < neutral_heat_below:
        return DECIDED_MODE_HEAT
    return DECIDED_MODE_NEUTRAL
