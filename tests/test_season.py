"""Unit tests for season.decide_mode — pure logic, no Home Assistant needed."""
from datetime import datetime

from smart_dual_thermostat.const import (
    DECIDED_MODE_COOL,
    DECIDED_MODE_HEAT,
    DECIDED_MODE_NEUTRAL,
    SEASON_MODE_CUSTOM_MONTHS,
    SEASON_MODE_HEMISPHERE,
    SEASON_MODE_TEMP_ONLY,
)
from smart_dual_thermostat.season import decide_mode

COMMON = dict(
    cool_season_heat_override_below=15.0,
    heat_season_cool_override_above=26.0,
    neutral_cool_above=22.0,
    neutral_heat_below=18.0,
)


def _decide(**overrides):
    kwargs = dict(
        season_mode=SEASON_MODE_HEMISPHERE,
        now=datetime(2026, 7, 15),
        latitude=41.0,
        custom_cool_months=None,
        custom_heat_months=None,
        outdoor_temp=28.0,
        **COMMON,
    )
    kwargs.update(overrides)
    return decide_mode(**kwargs)


def test_northern_summer_defaults_to_cool():
    assert _decide(now=datetime(2026, 7, 15), latitude=41.0, outdoor_temp=28.0) == DECIDED_MODE_COOL


def test_northern_winter_defaults_to_heat():
    assert _decide(now=datetime(2026, 1, 15), latitude=41.0, outdoor_temp=5.0) == DECIDED_MODE_HEAT


def test_southern_hemisphere_flips_seasons():
    # July in the southern hemisphere is winter -> heat, even though the
    # same calendar month is summer up north.
    assert _decide(now=datetime(2026, 7, 15), latitude=-33.0, outdoor_temp=8.0) == DECIDED_MODE_HEAT


def test_cool_season_cold_snap_overrides_to_heat():
    assert (
        _decide(now=datetime(2026, 7, 15), latitude=41.0, outdoor_temp=10.0)
        == DECIDED_MODE_HEAT
    )


def test_heat_season_heat_wave_overrides_to_cool():
    assert (
        _decide(now=datetime(2026, 1, 15), latitude=41.0, outdoor_temp=30.0)
        == DECIDED_MODE_COOL
    )


def test_shoulder_month_decides_by_temperature_alone():
    assert (
        _decide(now=datetime(2026, 4, 15), latitude=41.0, outdoor_temp=25.0)
        == DECIDED_MODE_COOL
    )
    assert (
        _decide(now=datetime(2026, 4, 15), latitude=41.0, outdoor_temp=10.0)
        == DECIDED_MODE_HEAT
    )
    assert (
        _decide(now=datetime(2026, 4, 15), latitude=41.0, outdoor_temp=20.0)
        == DECIDED_MODE_NEUTRAL
    )


def test_temp_only_mode_ignores_season_entirely():
    assert (
        _decide(
            season_mode=SEASON_MODE_TEMP_ONLY,
            now=datetime(2026, 1, 15),
            latitude=41.0,
            outdoor_temp=25.0,
        )
        == DECIDED_MODE_COOL
    )


def test_custom_months_used_when_configured():
    assert (
        _decide(
            season_mode=SEASON_MODE_CUSTOM_MONTHS,
            now=datetime(2026, 5, 1),
            custom_cool_months=[5, 6, 7, 8],
            custom_heat_months=[11, 12, 1, 2],
            outdoor_temp=25.0,
        )
        == DECIDED_MODE_COOL
    )


def test_no_outdoor_temp_falls_back_to_seasonal_default():
    assert (
        _decide(now=datetime(2026, 7, 15), latitude=41.0, outdoor_temp=None)
        == DECIDED_MODE_COOL
    )
