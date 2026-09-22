"""Per-actuator linear temperature correction.

Some real devices (e.g. certain Tuya-based thermostats) report/accept a
temperature attribute that does not match real degrees C — commonly a
fixed scale factor. Rather than hardcoding a single device's bug, each
actuator gets an optional (scale, offset) pair applied as:

    real_temp = device_temp * scale + offset
    device_temp = (real_temp - offset) / scale

Defaults to scale=1, offset=0 (no correction) for ordinary devices.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Correction:
    scale: float = 1.0
    offset: float = 0.0

    def to_real(self, device_value: float) -> float:
        return device_value * self.scale + self.offset

    def to_device(self, real_value: float) -> float:
        return (real_value - self.offset) / self.scale
