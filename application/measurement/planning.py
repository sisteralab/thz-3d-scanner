from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from application.measurement.config import MeasurementConfig


@dataclass(frozen=True)
class MeasurementPlan:
    freq_points: int
    base_steps_per_angle: int
    calibration_steps_per_angle: int
    rotation_points: int
    total_steps: int


def build_measurement_plan(config: MeasurementConfig) -> MeasurementPlan:
    freq_points = int(
        np.min([config.generator_1.freq_points, config.generator_2.freq_points])
    )
    base_steps_per_angle = (
        int(config.y_range.size) * int(config.x_range.size) * int(config.z_range.size)
    )
    full_z_lines = int(config.y_range.size) * int(config.x_range.size)
    calibration_steps_per_angle = 0
    if config.center_calibration.enabled and config.center_calibration.period_lines > 0:
        calibration_steps_per_angle = 1 + int(
            np.ceil(full_z_lines / config.center_calibration.period_lines)
        )
    rotation_points = int(config.rotation_range.size)
    total_steps = (
        rotation_points
        * (base_steps_per_angle + calibration_steps_per_angle)
        * freq_points
    )
    return MeasurementPlan(
        freq_points=freq_points,
        base_steps_per_angle=base_steps_per_angle,
        calibration_steps_per_angle=calibration_steps_per_angle,
        rotation_points=rotation_points,
        total_steps=total_steps,
    )


def normalize_amplitudes(
    amplitudes: list[float] | tuple[float, ...],
    freq_points: int,
) -> list[float | None]:
    values = list(amplitudes)
    if len(values) >= freq_points:
        return values[:freq_points]
    if values:
        return values + [values[-1] for _ in range(freq_points - len(values))]
    return [None for _ in range(freq_points)]
