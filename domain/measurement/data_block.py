from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


RAW_FLOAT_VOLUME_FIELDS = (
    "amplitude",
    "phase",
    "phase_degrees",
    "complex_real",
    "complex_imag",
    "z_request",
    "z_response",
    "vna_latency_ms",
)
CALIBRATED_FLOAT_VOLUME_FIELDS = (
    "calibrated_amplitude",
    "calibrated_phase",
    "calibrated_phase_degrees",
    "calibrated_complex_real",
    "calibrated_complex_imag",
)
FLOAT_VOLUME_FIELDS = RAW_FLOAT_VOLUME_FIELDS + CALIBRATED_FLOAT_VOLUME_FIELDS
BOOL_VOLUME_FIELDS = ("late_sample",)
PREVIEW_FIELDS = (
    "amplitude",
    "phase",
    "phase_degrees",
    "complex_real",
    "complex_imag",
    "calibrated_amplitude",
    "calibrated_phase",
    "calibrated_phase_degrees",
    "calibrated_complex_real",
    "calibrated_complex_imag",
    "z_request",
    "z_response",
    "late_sample",
    "vna_latency_ms",
)


@dataclass(frozen=True)
class MeasurementAxes:
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray

    @property
    def volume_shape(self) -> tuple[int, int, int]:
        return int(self.y.size), int(self.x.size), int(self.z.size)


def create_measurement_block(
    *,
    axes: MeasurementAxes,
    freq_1: float,
    freq_2: float,
    amp_1: float | None,
    amp_2: float | None,
    rotation_angle: float,
    center_calibration: dict[str, Any],
) -> dict[str, Any]:
    shape = axes.volume_shape
    block: dict[str, Any] = {
        "freq_1": freq_1,
        "amp_1": amp_1,
        "freq_2": freq_2,
        "amp_2": amp_2,
        "rotation_angle": float(rotation_angle),
        "x": axes.x.copy(),
        "y": axes.y.copy(),
        "z": axes.z.copy(),
        "center_calibration": dict(center_calibration),
        "calibration_points": [],
        "has_late_samples": False,
    }
    float_fields = list(RAW_FLOAT_VOLUME_FIELDS)
    if bool(center_calibration.get("enabled", False)):
        float_fields.extend(CALIBRATED_FLOAT_VOLUME_FIELDS)
    for field in float_fields:
        block[field] = np.zeros(shape, dtype=np.float32)
    for field in BOOL_VOLUME_FIELDS:
        block[field] = np.zeros(shape, dtype=bool)
    return block


def create_preview_view(block: dict[str, Any]) -> dict[str, Any]:
    preview = {
        "freq_1": block["freq_1"],
        "amp_1": block["amp_1"],
        "freq_2": block["freq_2"],
        "amp_2": block["amp_2"],
        "rotation_angle": block["rotation_angle"],
        "has_late_samples": block.get("has_late_samples", False),
        "x": block["x"],
        "y": block["y"],
        "z": block["z"],
    }
    for field in PREVIEW_FIELDS:
        if field in block:
            preview[field] = block[field]
    return preview
