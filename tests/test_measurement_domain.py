import unittest

import numpy as np

from application.measurement.config import (
    CenterCalibrationConfig,
    GeneratorSweepConfig,
    MeasurementConfig,
    MovementTimingConfig,
    SweepModeConfig,
    VnaConfig,
)
from application.measurement.planning import (
    build_measurement_plan,
    normalize_amplitudes,
)
from domain.measurement.data_block import (
    MeasurementAxes,
    create_measurement_block,
    create_preview_view,
)
from domain.measurement.sample import build_complex_sample
from store.data import MeasureModel


class MeasurementDomainTest(unittest.TestCase):
    def _config(self, calibration_enabled=False):
        return MeasurementConfig(
            x_range=np.arange(3, dtype=np.float32),
            y_range=np.arange(2, dtype=np.float32),
            z_range=np.arange(4, dtype=np.float32),
            rotation_range=np.array([0.0], dtype=np.float32),
            vna=VnaConfig(-30, 0.0, 1.0, 2, 1000, 1, False),
            generator_1=GeneratorSweepConfig(1.0, 2.0, 2, (1.0,)),
            generator_2=GeneratorSweepConfig(1.0, 2.0, 2, ()),
            sweep=SweepModeConfig(True, True, True, True, False, 1.0, False, False),
            movement=MovementTimingConfig(1, 1, 1, 1, 1),
            center_calibration=CenterCalibrationConfig(
                calibration_enabled,
                0.0,
                0.0,
                0.0,
                2,
            ),
            plot_update_hz=10.0,
        )

    def test_measurement_plan_includes_calibration_points(self):
        plan = build_measurement_plan(self._config(calibration_enabled=True))
        self.assertEqual(plan.base_steps_per_angle, 24)
        self.assertEqual(plan.calibration_steps_per_angle, 4)
        self.assertEqual(plan.total_steps, 56)

    def test_amplitudes_are_extended_without_mutating_source(self):
        source = (1.0,)
        self.assertEqual(normalize_amplitudes(source, 3), [1.0, 1.0, 1.0])
        self.assertEqual(source, (1.0,))

    def test_data_block_allocates_calibrated_arrays_only_when_needed(self):
        axes = MeasurementAxes(
            x=np.arange(3, dtype=np.float32),
            y=np.arange(2, dtype=np.float32),
            z=np.arange(4, dtype=np.float32),
        )
        raw = create_measurement_block(
            axes=axes,
            freq_1=1.0,
            freq_2=1.0,
            amp_1=None,
            amp_2=None,
            rotation_angle=0.0,
            center_calibration={"enabled": False},
        )
        calibrated = create_measurement_block(
            axes=axes,
            freq_1=1.0,
            freq_2=1.0,
            amp_1=None,
            amp_2=None,
            rotation_angle=0.0,
            center_calibration={"enabled": True},
        )
        self.assertEqual(raw["amplitude"].dtype, np.float32)
        self.assertNotIn("calibrated_amplitude", raw)
        self.assertIn("calibrated_amplitude", calibrated)
        self.assertIs(create_preview_view(raw)["amplitude"], raw["amplitude"])

    def test_measure_model_serializes_numpy_only_on_save(self):
        model = MeasureModel(
            data=[{"amplitude": np.zeros((2, 3), dtype=np.float32)}],
        )
        payload = model.to_json()
        self.assertIsInstance(payload["data"][0]["amplitude"], list)

    def test_complex_sample_dto_from_vna_arrays(self):
        sample = build_complex_sample(
            {
                "real": np.array([1.0, 1.0], dtype=np.float32),
                "imag": np.array([0.0, 0.0], dtype=np.float32),
            },
            latency_s=0.012,
        )
        self.assertIsNotNone(sample)
        self.assertAlmostEqual(sample.real, 1.0)
        self.assertAlmostEqual(sample.imag, 0.0)
        self.assertAlmostEqual(sample.amplitude_db, 0.0)
        self.assertAlmostEqual(sample.phase_rad, 0.0)
        self.assertAlmostEqual(sample.latency_ms, 12.0)


if __name__ == "__main__":
    unittest.main()
