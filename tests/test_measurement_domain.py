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
    AxisMotionProfile,
    MotionProfiles,
    build_measurement_plan,
    estimate_measurement_seconds,
    estimate_motion_time_s,
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

    def test_motion_time_uses_trapezoid_profile(self):
        profile = AxisMotionProfile(speed=10.0, accel=10.0, decel=10.0)
        self.assertAlmostEqual(estimate_motion_time_s(20.0, profile), 3.0)

    def test_fly_estimate_uses_configured_speed(self):
        slow = self._config()
        fast = MeasurementConfig(
            x_range=slow.x_range,
            y_range=slow.y_range,
            z_range=np.linspace(0.0, 10.0, 11, dtype=np.float32),
            rotation_range=slow.rotation_range,
            vna=slow.vna,
            generator_1=slow.generator_1,
            generator_2=slow.generator_2,
            sweep=SweepModeConfig(True, True, True, False, True, 20.0, False, False),
            movement=slow.movement,
            center_calibration=slow.center_calibration,
            plot_update_hz=slow.plot_update_hz,
        )
        slow = MeasurementConfig(
            x_range=fast.x_range,
            y_range=fast.y_range,
            z_range=fast.z_range,
            rotation_range=fast.rotation_range,
            vna=VnaConfig(-30, 0.0, 0.01, 2, 1000, 1, False),
            generator_1=fast.generator_1,
            generator_2=fast.generator_2,
            sweep=SweepModeConfig(True, True, True, False, True, 2.0, False, False),
            movement=fast.movement,
            center_calibration=fast.center_calibration,
            plot_update_hz=fast.plot_update_hz,
        )
        fast = MeasurementConfig(
            x_range=fast.x_range,
            y_range=fast.y_range,
            z_range=fast.z_range,
            rotation_range=fast.rotation_range,
            vna=slow.vna,
            generator_1=fast.generator_1,
            generator_2=fast.generator_2,
            sweep=fast.sweep,
            movement=fast.movement,
            center_calibration=fast.center_calibration,
            plot_update_hz=fast.plot_update_hz,
        )

        motion = MotionProfiles(
            x=AxisMotionProfile(100.0, 100.0, 100.0),
            y=AxisMotionProfile(100.0, 100.0, 100.0),
            z=AxisMotionProfile(100.0, 100.0, 100.0),
            rotation=AxisMotionProfile(100.0, 100.0, 100.0),
        )
        self.assertLess(
            estimate_measurement_seconds(fast, motion),
            estimate_measurement_seconds(slow, motion),
        )

    def test_estimate_includes_vna_average_and_cw_points(self):
        base = self._config()
        averaged_cw = MeasurementConfig(
            x_range=base.x_range,
            y_range=base.y_range,
            z_range=base.z_range,
            rotation_range=base.rotation_range,
            vna=VnaConfig(
                -30,
                0.0,
                0.1,
                2,
                1000,
                4,
                True,
                cw_frequency_enabled=True,
                cw_frequency_points=3,
            ),
            generator_1=base.generator_1,
            generator_2=base.generator_2,
            sweep=base.sweep,
            movement=base.movement,
            center_calibration=base.center_calibration,
            plot_update_hz=base.plot_update_hz,
        )
        motion = MotionProfiles(
            x=AxisMotionProfile(100.0, 100.0, 100.0),
            y=AxisMotionProfile(100.0, 100.0, 100.0),
            z=AxisMotionProfile(100.0, 100.0, 100.0),
            rotation=AxisMotionProfile(100.0, 100.0, 100.0),
        )
        self.assertGreater(
            estimate_measurement_seconds(averaged_cw, motion),
            estimate_measurement_seconds(base, motion),
        )

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
