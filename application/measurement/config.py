from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from api.vna import DEFAULT_VNA_PARAMETER


@dataclass(frozen=True)
class VnaConfig:
    power: float
    start_time: float
    stop_time: float
    points: int
    bandwidth: int
    average_count: int
    average_enabled: bool
    parameter: str = DEFAULT_VNA_PARAMETER
    output_enabled: bool = True
    cw_frequency_enabled: bool = False
    cw_frequency_start_ghz: float = 1.0
    cw_frequency_stop_ghz: float = 1.0
    cw_frequency_points: int = 1


@dataclass(frozen=True)
class GeneratorSweepConfig:
    freq_start: float
    freq_stop: float
    freq_points: int
    amplitudes: tuple[float, ...]


@dataclass(frozen=True)
class SweepModeConfig:
    use_x: bool
    use_y: bool
    use_z: bool
    use_z_snake_pattern: bool
    use_z_fly_mode: bool
    z_fly_speed: float
    auto_adjust_z_fly_speed: bool
    use_rotation: bool


@dataclass(frozen=True)
class MovementTimingConfig:
    x_delay_ms: int
    y_delay_ms: int
    z_delay_ms: int
    no_movement_delay_ms: int
    fly_poll_delay_ms: int


@dataclass(frozen=True)
class CenterCalibrationConfig:
    enabled: bool
    x: float
    y: float
    z: float
    period_lines: int


@dataclass(frozen=True)
class MeasurementConfig:
    x_range: np.ndarray
    y_range: np.ndarray
    z_range: np.ndarray
    rotation_range: np.ndarray
    vna: VnaConfig
    generator_1: GeneratorSweepConfig
    generator_2: GeneratorSweepConfig
    sweep: SweepModeConfig
    movement: MovementTimingConfig
    center_calibration: CenterCalibrationConfig
    plot_update_hz: float
    use_generators: bool = True


def parse_amplitudes(raw_value: str) -> tuple[float, ...]:
    amplitudes: list[float] = []
    for raw_item in raw_value.replace(" ", "").split(","):
        try:
            amplitudes.append(float(raw_item))
        except ValueError:
            continue
    return tuple(amplitudes)


def build_axis_range(
    *,
    start: float,
    stop: float,
    points: int,
    enabled: bool,
) -> np.ndarray:
    if not enabled:
        return np.array([0.0], dtype=np.float32)
    return np.linspace(start, stop, points, dtype=np.float32)
