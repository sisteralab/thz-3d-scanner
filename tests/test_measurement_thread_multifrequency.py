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
from api.vna import DEFAULT_VNA_PARAMETER, normalize_vna_parameter
from infrastructure.measurement.qt_measure_thread import MeasureThread


class FakeVna:
    def __init__(self):
        self.powers = []
        self.parameters = []
        self.output_states = []
        self.cw_frequencies = []

    def __getattr__(self, name):
        if name.startswith("set_") or name == "set_parameter":
            return lambda *args, **kwargs: None
        raise AttributeError(name)

    def set_power(self, value):
        self.powers.append(float(value))

    def set_parameter(self, value):
        self.parameters.append(str(value))

    def set_output_state(self, value):
        self.output_states.append(bool(value))

    def set_cw_frequency(self, value):
        self.cw_frequencies.append(float(value))

    @staticmethod
    def get_data():
        return {
            "real": np.array([1.0, 1.0], dtype=np.float32),
            "imag": np.array([0.0, 0.0], dtype=np.float32),
        }


class FakeGenerator:
    def __init__(self):
        self.frequencies = []
        self.powers = []

    def set_frequency(self, value):
        self.frequencies.append(float(value))

    def set_power(self, value):
        self.powers.append(value)


class FakeScanner:
    id_x = None
    id_y = None
    id_z = None
    id_rotation = None
    rotation_unit = None

    @staticmethod
    def get_position(*_args, **_kwargs):
        return 0.0


class FakeRuntime:
    def __init__(self):
        self.scanner = FakeScanner()
        self.vna = FakeVna()
        self.generator_1 = FakeGenerator()
        self.generator_2 = FakeGenerator()
        self.scanner_z_speed = 1.0
        self.scanner_z_accel = 1.0
        self.scanner_z_decel = 1.0

    @staticmethod
    def is_measure_running():
        return True

    @staticmethod
    def plot_update_hz(fallback):
        return fallback


def build_config():
    return MeasurementConfig(
        x_range=np.array([0.0], dtype=np.float32),
        y_range=np.array([0.0], dtype=np.float32),
        z_range=np.array([0.0], dtype=np.float32),
        rotation_range=np.array([0.0], dtype=np.float32),
        vna=VnaConfig(-30.0, 0.0, 1.0, 2, 1000, 1, False),
        generator_1=GeneratorSweepConfig(1.0, 3.0, 3, ()),
        generator_2=GeneratorSweepConfig(10.0, 30.0, 3, ()),
        sweep=SweepModeConfig(False, False, False, False, False, 1.0, False, False),
        movement=MovementTimingConfig(1, 1, 1, 1, 1),
        center_calibration=CenterCalibrationConfig(False, 0.0, 0.0, 0.0, 0),
        plot_update_hz=1000.0,
    )


class MeasurementThreadMultiFrequencyTest(unittest.TestCase):
    def test_invalid_vna_parameter_falls_back_to_default_ratio_name(self):
        self.assertEqual(normalize_vna_parameter("BA"), DEFAULT_VNA_PARAMETER)
        self.assertEqual(normalize_vna_parameter("AB"), DEFAULT_VNA_PARAMETER)

    def test_configured_vna_power_is_applied(self):
        runtime = FakeRuntime()
        config = build_config()
        config = MeasurementConfig(
            x_range=config.x_range,
            y_range=config.y_range,
            z_range=config.z_range,
            rotation_range=config.rotation_range,
            vna=VnaConfig(-17.5, 0.0, 1.0, 2, 1000, 1, False),
            generator_1=config.generator_1,
            generator_2=config.generator_2,
            sweep=config.sweep,
            movement=config.movement,
            center_calibration=config.center_calibration,
            plot_update_hz=config.plot_update_hz,
        )
        thread = MeasureThread(config=config, runtime=runtime)

        thread.run()

        self.assertEqual(runtime.vna.powers, [-17.5])

    def test_configured_vna_parameter_is_applied(self):
        runtime = FakeRuntime()
        config = build_config()
        config = MeasurementConfig(
            x_range=config.x_range,
            y_range=config.y_range,
            z_range=config.z_range,
            rotation_range=config.rotation_range,
            vna=VnaConfig(-30.0, 0.0, 1.0, 2, 1000, 1, False, "S21"),
            generator_1=config.generator_1,
            generator_2=config.generator_2,
            sweep=config.sweep,
            movement=config.movement,
            center_calibration=config.center_calibration,
            plot_update_hz=config.plot_update_hz,
        )
        thread = MeasureThread(config=config, runtime=runtime)

        thread.run()

        self.assertEqual(runtime.vna.parameters, ["S21"])

    def test_configured_vna_output_state_is_applied(self):
        runtime = FakeRuntime()
        config = build_config()
        config = MeasurementConfig(
            x_range=config.x_range,
            y_range=config.y_range,
            z_range=config.z_range,
            rotation_range=config.rotation_range,
            vna=VnaConfig(-30.0, 0.0, 1.0, 2, 1000, 1, False, "B2/A1", False),
            generator_1=config.generator_1,
            generator_2=config.generator_2,
            sweep=config.sweep,
            movement=config.movement,
            center_calibration=config.center_calibration,
            plot_update_hz=config.plot_update_hz,
        )
        thread = MeasureThread(config=config, runtime=runtime)

        thread.run()

        self.assertEqual(runtime.vna.output_states, [False])

    def test_vna_cw_frequency_sweep_creates_blocks_and_sets_frequency(self):
        runtime = FakeRuntime()
        config = build_config()
        config = MeasurementConfig(
            x_range=config.x_range,
            y_range=config.y_range,
            z_range=config.z_range,
            rotation_range=config.rotation_range,
            vna=VnaConfig(
                -30.0,
                0.0,
                1.0,
                2,
                1000,
                1,
                False,
                "B2/A1",
                True,
                True,
                1.0,
                1.5,
                2,
            ),
            generator_1=GeneratorSweepConfig(1.0, 1.0, 1, ()),
            generator_2=GeneratorSweepConfig(10.0, 10.0, 1, ()),
            sweep=config.sweep,
            movement=config.movement,
            center_calibration=config.center_calibration,
            plot_update_hz=config.plot_update_hz,
        )
        thread = MeasureThread(config=config, runtime=runtime)

        thread.run()

        self.assertEqual(runtime.vna.cw_frequencies, [1.0e9, 1.5e9])
        self.assertEqual(len(thread.measure.data), 2)
        self.assertEqual(
            [block["vna_cw_frequency_hz"] for block in thread.measure.data],
            [1.0e9, 1.5e9],
        )

    def test_all_frequency_blocks_are_stored_including_last(self):
        runtime = FakeRuntime()
        thread = MeasureThread(config=build_config(), runtime=runtime)
        preview_storage_lengths = []

        def on_preview(payload):
            preview_storage_lengths.append(
                (float(payload["freq_1"]), len(thread.measure.data))
            )

        thread.data.connect(on_preview)
        thread.run()

        self.assertEqual(len(thread.measure.data), 3)
        self.assertEqual(
            [float(block["freq_1"]) for block in thread.measure.data],
            [1.0, 2.0, 3.0],
        )
        self.assertEqual(
            [float(block["freq_2"]) for block in thread.measure.data],
            [10.0, 20.0, 30.0],
        )
        self.assertEqual(runtime.generator_1.frequencies, [1e9, 2e9, 3e9])
        self.assertEqual(runtime.generator_2.frequencies, [10e9, 20e9, 30e9])
        self.assertIn((3.0, 3), preview_storage_lengths)
        for block in thread.measure.data:
            self.assertEqual(block["amplitude"].shape, (1, 1, 1))
            self.assertAlmostEqual(float(block["amplitude"][0, 0, 0]), 0.0)

    def test_measurement_can_run_without_generators(self):
        runtime = FakeRuntime()
        runtime.generator_1 = None
        runtime.generator_2 = None
        base = build_config()
        config = MeasurementConfig(
            x_range=base.x_range,
            y_range=base.y_range,
            z_range=base.z_range,
            rotation_range=base.rotation_range,
            vna=base.vna,
            generator_1=base.generator_1,
            generator_2=base.generator_2,
            sweep=base.sweep,
            movement=base.movement,
            center_calibration=base.center_calibration,
            plot_update_hz=base.plot_update_hz,
            use_generators=False,
        )
        thread = MeasureThread(config=config, runtime=runtime)

        thread.run()

        self.assertEqual(len(thread.measure.data), 1)
        self.assertIsNone(thread.measure.data[0]["freq_1"])
        self.assertIsNone(thread.measure.data[0]["freq_2"])
        self.assertIsNone(thread.measure.data[0]["amp_1"])
        self.assertIsNone(thread.measure.data[0]["amp_2"])

    def test_z_fly_auto_speed_can_raise_after_fast_vna_response(self):
        base = build_config()
        config = MeasurementConfig(
            x_range=base.x_range,
            y_range=base.y_range,
            z_range=np.array([0.0, 1.0, 2.0], dtype=np.float32),
            rotation_range=base.rotation_range,
            vna=base.vna,
            generator_1=base.generator_1,
            generator_2=base.generator_2,
            sweep=SweepModeConfig(False, False, True, False, True, 10.0, True, False),
            movement=MovementTimingConfig(1, 1, 1, 1, 1),
            center_calibration=base.center_calibration,
            plot_update_hz=base.plot_update_hz,
        )
        thread = MeasureThread(config=config, runtime=FakeRuntime())
        thread._build_z_profiles()

        thread._last_vna_latency_s = 0.5
        thread._limit_z_fly_speed_for_latency(min_step=1.0, tolerance=0.45)
        slow_speed = thread._z_fly_profile["speed"]
        self.assertLess(slow_speed, 10.0)

        thread._last_vna_latency_s = 0.001
        thread._limit_z_fly_speed_for_latency(min_step=1.0, tolerance=0.45)
        raised_speed = thread._z_fly_profile["speed"]

        self.assertGreater(raised_speed, slow_speed)
        self.assertLessEqual(raised_speed, 10.0)

    def test_final_signal_is_emitted_after_measure_is_finished(self):
        thread = MeasureThread(config=build_config(), runtime=FakeRuntime())
        finished_values = []

        def on_final(_payload):
            finished_values.append(thread.measure.finished)

        thread.final_data.connect(on_final)
        thread.run()

        self.assertEqual(len(finished_values), 1)
        self.assertNotEqual(finished_values[0], "--")


if __name__ == "__main__":
    unittest.main()
