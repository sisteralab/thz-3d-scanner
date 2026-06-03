from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CalibrationSample:
    line_number: int
    complex_value: complex


def interpolate_calibration(
    previous_sample: CalibrationSample,
    current_sample: CalibrationSample,
    line_number: int,
) -> complex:
    span = max(1, current_sample.line_number - previous_sample.line_number)
    ratio = (int(line_number) - previous_sample.line_number) / span
    return (
        previous_sample.complex_value
        + (current_sample.complex_value - previous_sample.complex_value) * ratio
    )


def calibration_factor(
    reference_complex: complex, line_calibration: complex
) -> complex:
    if abs(line_calibration) <= 1e-12:
        return 1.0 + 0.0j
    return reference_complex / line_calibration


def apply_complex_factor(
    raw_real: np.ndarray,
    raw_imag: np.ndarray,
    factor: complex,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    corrected = (
        raw_real.astype(np.float64) + 1j * raw_imag.astype(np.float64)
    ) * factor
    corrected_real = np.real(corrected).astype(np.float32, copy=False)
    corrected_imag = np.imag(corrected).astype(np.float32, copy=False)
    corrected_amplitude = (
        20 * np.log10(np.clip(np.abs(corrected), 1e-12, None))
    ).astype(np.float32, copy=False)
    corrected_phase = np.angle(corrected).astype(np.float32, copy=False)
    return corrected_real, corrected_imag, corrected_amplitude, corrected_phase
