from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class ComplexMeasurementSample:
    real: float
    imag: float
    amplitude_db: float
    phase_rad: float
    latency_ms: float

    @property
    def complex_value(self) -> complex:
        return complex(self.real, self.imag)

    @property
    def phase_degrees(self) -> float:
        return float(self.phase_rad * (180.0 / np.pi))


def build_complex_sample(
    vna_data: dict[str, Any],
    *,
    latency_s: float,
) -> ComplexMeasurementSample | None:
    real = np.asarray(vna_data.get("real", []), dtype=np.float32)
    imag = np.asarray(vna_data.get("imag", []), dtype=np.float32)
    points_count = int(min(real.size, imag.size))
    if points_count == 0:
        return None

    mean_real = float(np.mean(real[:points_count], dtype=np.float64))
    mean_imag = float(np.mean(imag[:points_count], dtype=np.float64))
    amplitude_db = float(20 * np.log10(max(np.hypot(mean_real, mean_imag), 1e-12)))
    phase_rad = float(np.arctan2(mean_imag, mean_real))
    return ComplexMeasurementSample(
        real=mean_real,
        imag=mean_imag,
        amplitude_db=amplitude_db,
        phase_rad=phase_rad,
        latency_ms=float(latency_s * 1000.0),
    )
