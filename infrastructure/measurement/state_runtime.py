from __future__ import annotations

from dataclasses import dataclass

from store.state import State


@dataclass(frozen=True)
class StateMeasurementRuntime:
    scanner: object
    vna: object
    generator_1: object
    generator_2: object
    scanner_z_speed: float
    scanner_z_accel: float
    scanner_z_decel: float

    @classmethod
    def from_state(cls) -> "StateMeasurementRuntime":
        return cls(
            scanner=State.scanner,
            vna=State.vna,
            generator_1=State.generator_1,
            generator_2=State.generator_2,
            scanner_z_speed=State.scanner_z_speed,
            scanner_z_accel=State.scanner_z_accel,
            scanner_z_decel=State.scanner_z_decel,
        )

    @staticmethod
    def is_measure_running() -> bool:
        return bool(State.measure_running)

    @staticmethod
    def plot_update_hz(fallback: float) -> float:
        return float(getattr(State, "plot_update_hz", fallback))
