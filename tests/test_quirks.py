"""Unit tests for quirks.Correction."""
from smart_dual_thermostat.quirks import Correction


def test_default_correction_is_identity():
    c = Correction()
    assert c.to_real(21.0) == 21.0
    assert c.to_device(21.0) == 21.0


def test_tuya_scale_5_bug_round_trips():
    c = Correction(scale=5.0)
    device_value = 4.2
    real_value = c.to_real(device_value)
    assert real_value == 21.0
    assert c.to_device(real_value) == device_value


def test_offset_applies_after_scale():
    c = Correction(scale=1.0, offset=2.0)
    assert c.to_real(20.0) == 22.0
    assert c.to_device(22.0) == 20.0
