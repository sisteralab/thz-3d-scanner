from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QThread, Signal

from api.vna import normalize_vna_parameter
from application.measurement.config import MeasurementConfig
from application.measurement.planning import (
    build_measurement_plan,
    normalize_amplitudes,
)
from application.measurement.ports import MeasurementRuntimePort
from domain.measurement.calibration import (
    CalibrationSample,
    apply_complex_factor,
    calibration_factor,
    interpolate_calibration,
)
from domain.measurement.data_block import (
    MeasurementAxes,
    create_measurement_block,
    create_preview_view,
)
from domain.measurement.sample import build_complex_sample
from infrastructure.measurement.state_runtime import StateMeasurementRuntime
from store.data import MeasureModel
from utils.functions import convert_seconds


class MeasureThread(QThread):
    data = Signal(dict)
    final_data = Signal(list)
    progress = Signal(int)
    remaining_time = Signal(str)
    log = Signal(dict)

    def __init__(
        self,
        config: MeasurementConfig,
        runtime: MeasurementRuntimePort | None = None,
    ):
        super().__init__()
        self.runtime = runtime or StateMeasurementRuntime.from_state()
        self.config = config
        self.x_range = np.asarray(config.x_range, dtype=np.float32)
        self.y_range = np.asarray(config.y_range, dtype=np.float32)
        self.z_range = np.asarray(config.z_range, dtype=np.float32)
        self.rotation_range = np.asarray(config.rotation_range, dtype=np.float32)
        self.vna_power = config.vna.power
        self.vna_parameter = normalize_vna_parameter(config.vna.parameter)
        self.vna_output_enabled = bool(config.vna.output_enabled)
        self.vna_cw_frequency_enabled = bool(config.vna.cw_frequency_enabled)
        self.vna_cw_frequency_start_ghz = float(config.vna.cw_frequency_start_ghz)
        self.vna_cw_frequency_stop_ghz = float(config.vna.cw_frequency_stop_ghz)
        self.vna_cw_frequency_points = max(1, int(config.vna.cw_frequency_points))
        self.vna_start = config.vna.start_time
        self.vna_stop = config.vna.stop_time
        self.vna_points = config.vna.points
        self.generator_freq_start_1 = config.generator_1.freq_start
        self.generator_freq_stop_1 = config.generator_1.freq_stop
        self.generator_freq_points_1 = config.generator_1.freq_points
        self.generator_amps_1 = config.generator_1.amplitudes
        self.generator_freq_start_2 = config.generator_2.freq_start
        self.generator_freq_stop_2 = config.generator_2.freq_stop
        self.generator_freq_points_2 = config.generator_2.freq_points
        self.generator_amps_2 = config.generator_2.amplitudes
        self.use_generators = bool(config.use_generators)
        self.vna_bandwidth = config.vna.bandwidth
        self.vna_average_count = config.vna.average_count
        self.vna_average_enabled = config.vna.average_enabled
        self.use_x_sweep = config.sweep.use_x
        self.use_y_sweep = config.sweep.use_y
        self.use_z_sweep = config.sweep.use_z
        self.use_z_snake_pattern = config.sweep.use_z_snake_pattern
        self.use_z_fly_mode = config.sweep.use_z_fly_mode
        self.z_fly_speed = config.sweep.z_fly_speed
        self.auto_adjust_z_fly_speed = config.sweep.auto_adjust_z_fly_speed
        self.use_rotation_sweep = config.sweep.use_rotation
        self.plot_update_hz = max(0.01, float(config.plot_update_hz))
        self._last_preview_emit_time = 0.0
        self.x_movement_delay = config.movement.x_delay_ms
        self.y_movement_delay = config.movement.y_delay_ms
        self.z_movement_delay = config.movement.z_delay_ms
        self.no_movement_delay = config.movement.no_movement_delay_ms
        self.fly_poll_delay_ms = config.movement.fly_poll_delay_ms
        self.center_calibration_enabled = bool(config.center_calibration.enabled)
        self.center_calibration_x = float(config.center_calibration.x)
        self.center_calibration_y = float(config.center_calibration.y)
        self.center_calibration_z = float(config.center_calibration.z)
        self.center_calibration_period_lines = max(
            0,
            int(config.center_calibration.period_lines),
        )
        self._step_counter = 0
        self._total_steps = 0
        self._start_time = 0.0
        self._z_fast_profile = None
        self._z_fly_profile = None
        self._last_vna_latency_s = 0.0

        self.measure = MeasureModel.objects.create(data=[])
        self.measure.save(False)

    @staticmethod
    def _format_frequency(freq_ghz):
        if freq_ghz is None:
            return "off"
        return f"{float(freq_ghz):.5f}GHz"

    @staticmethod
    def _optional_float(value):
        if value is None:
            return None
        return float(value)

    @classmethod
    def from_config(
        cls,
        config: MeasurementConfig,
        runtime: MeasurementRuntimePort | None = None,
    ) -> "MeasureThread":
        return cls(config=config, runtime=runtime)

    def _preview_emit_interval_s(self):
        update_hz = max(
            0.01,
            self.runtime.plot_update_hz(self.plot_update_hz),
        )
        return 1.0 / update_hz

    def _emit_preview_data(self, preview_data, force=False):
        now = time.monotonic()
        if (
            not force
            and now - self._last_preview_emit_time < self._preview_emit_interval_s()
        ):
            return
        self._last_preview_emit_time = now
        self.data.emit(preview_data)

    def _configure_vna(self):
        self.runtime.vna.set_parameter(self.vna_parameter)
        try:
            self.runtime.vna.set_start_time(self.vna_start)
            self.runtime.vna.set_stop_time(self.vna_stop)
        except Exception as err:
            self.log.emit(
                {
                    "type": "warning",
                    "msg": f"Failed to apply VNA start/stop time: {err}",
                }
            )
        self.runtime.vna.set_sweep(max(1, int(self.vna_points)))
        self.runtime.vna.set_power(self.vna_power)
        self.runtime.vna.set_output_state(self.vna_output_enabled)
        self.runtime.vna.set_channel_format("COMP")
        self.runtime.vna.set_average_count(max(1, int(self.vna_average_count)))
        self.runtime.vna.set_average_status(bool(self.vna_average_enabled))
        self.runtime.vna.set_bandwidth(max(1, int(self.vna_bandwidth)))

    def _vna_cw_frequency_range_hz(self):
        if not self.vna_cw_frequency_enabled:
            return [None]
        return [
            float(value) * 1e9
            for value in np.linspace(
                self.vna_cw_frequency_start_ghz,
                self.vna_cw_frequency_stop_ghz,
                self.vna_cw_frequency_points,
            )
        ]

    @staticmethod
    def _smooth_move_profile(profile, ramp_time_s: float, min_accel: float = 1.0):
        speed = abs(float(profile.get("speed", 0.0)))
        if speed <= 0:
            return profile

        max_accel = max(float(min_accel), speed / max(float(ramp_time_s), 0.001))
        accel = float(profile.get("accel", max_accel))
        decel = float(profile.get("decel", max_accel))
        profile = dict(profile)
        profile["accel"] = min(accel, max_accel) if accel > 0 else max_accel
        profile["decel"] = min(decel, max_accel) if decel > 0 else max_accel
        return profile

    def _build_z_profiles(self):
        if not (self.use_z_fly_mode and self.use_z_sweep):
            self._z_fast_profile = None
            self._z_fly_profile = None
            return

        fly_speed = float(self.z_fly_speed)
        fallback_fast_speed = float(self.runtime.scanner_z_speed)
        fallback_fast_accel = float(self.runtime.scanner_z_accel)
        fallback_fast_decel = float(self.runtime.scanner_z_decel)

        try:
            self._z_fast_profile = self.runtime.scanner.get_move_settings(
                self.runtime.scanner.id_z
            )
        except Exception:
            self._z_fast_profile = None

        if not self._z_fast_profile:
            # Fallback profile in case current settings cannot be read from controller.
            self._z_fast_profile = {
                "speed": fallback_fast_speed,
                "accel": fallback_fast_accel,
                "decel": fallback_fast_decel,
            }
            self.log.emit(
                {
                    "type": "warning",
                    "msg": (
                        "Could not read default Z move profile; "
                        "using Scanner Init Z move profile."
                    ),
                }
            )
        fly_accel = max(1.0, fly_speed * 5.0)
        self._z_fly_profile = {
            "speed": fly_speed,
            "accel": fly_accel,
            "decel": fly_accel,
        }

    def _limit_z_fly_speed_for_latency(self, min_step: float, tolerance: float):
        if not self._z_fly_profile or min_step <= 0:
            return

        requested_speed = abs(float(self._z_fly_profile.get("speed", self.z_fly_speed)))
        if requested_speed <= 0:
            return

        latency_s = max(float(self._last_vna_latency_s), 0.001)
        poll_s = max(0.001, float(self.fly_poll_delay_ms) / 1000.0)
        sample_budget_s = latency_s + poll_s + 0.02
        safe_by_sample = 0.8 * float(min_step) / sample_budget_s
        safe_by_poll = 0.8 * (2.0 * float(tolerance)) / poll_s
        safe_speed = max(0.001, min(safe_by_sample, safe_by_poll))
        if requested_speed <= safe_speed:
            return

        accel = max(1.0, safe_speed * 5.0)
        self._z_fly_profile = {
            "speed": safe_speed,
            "accel": accel,
            "decel": accel,
        }
        self.log.emit(
            {
                "type": "warning",
                "msg": (
                    "Z fly speed limited by VNA latency: "
                    f"requested={requested_speed:.4f}, safe={safe_speed:.4f}, "
                    f"latency={latency_s * 1000.0:.1f} ms, step={min_step:.4f}"
                ),
            }
        )

    def _z_fly_ramp_distance(self):
        if not self._z_fly_profile:
            return 0.0
        speed = abs(float(self._z_fly_profile.get("speed", self.z_fly_speed)))
        accel = abs(float(self._z_fly_profile.get("accel", 0.0)))
        if speed <= 0 or accel <= 0:
            return 0.0
        return float((speed * speed) / (2.0 * accel))

    def _probe_vna_latency(self):
        started = time.time()
        self.runtime.vna.get_data()
        self._last_vna_latency_s = time.time() - started
        self.log.emit(
            {
                "type": "info",
                "msg": f"VNA latency probe {self._last_vna_latency_s * 1000.0:.1f} ms",
            }
        )

    def _apply_z_profile(self, profile):
        if not profile:
            return
        try:
            self.runtime.scanner.set_move_settings(
                self.runtime.scanner.id_z,
                float(profile["speed"]),
                float(profile["accel"]),
                float(profile["decel"]),
            )
        except Exception as err:
            self.log.emit({"type": "warning", "msg": f"Failed to set Z profile: {err}"})

    def _update_progress(self):
        if self._total_steps <= 0:
            return

        self.progress.emit(int(round(self._step_counter * 100 / self._total_steps)))

        elapsed = max(time.time() - self._start_time, 1e-6)
        velocity = self._step_counter / elapsed
        if velocity <= 0:
            self.remaining_time.emit("Approx time ~ calculating...")
            return

        remaining = max(0, round((self._total_steps - self._step_counter) / velocity))
        self.remaining_time.emit(f"Approx time ~ {convert_seconds(remaining)}")

    def _rotation_move_timeout_s(self, current_angle, target_angle):
        travel = abs(float(target_angle) - float(current_angle))
        return max(5.0, travel / 10.0 * 4.0 + 5.0)

    def _capture_point(
        self,
        full_data,
        preview_data,
        step_y,
        step_x,
        z_idx,
        z_target,
        freq_1,
        freq_2,
        late_sample=False,
        sample_tolerance=None,
    ):
        z_request = float(z_target)
        if self.use_z_sweep:
            try:
                z_request = float(
                    self.runtime.scanner.get_position(self.runtime.scanner.id_z)
                )
            except Exception:
                ...
        m_s_time = time.time()
        vna_data = self.runtime.vna.get_data()
        meas_duration = time.time() - m_s_time
        self._last_vna_latency_s = meas_duration
        z_response = z_request
        if self.use_z_sweep:
            try:
                z_response = float(
                    self.runtime.scanner.get_position(self.runtime.scanner.id_z)
                )
            except Exception:
                ...
        sample = build_complex_sample(vna_data, latency_s=meas_duration)
        if sample is None:
            return False
        self.log.emit(
            {
                "type": "info",
                "msg": (
                    f"freq1 {self._format_frequency(freq_1)}; "
                    f"freq2 {self._format_frequency(freq_2)}; "
                    f"pow {sample.amplitude_db:.5f} dB; "
                    f"phase {sample.phase_rad:.2f}"
                ),
            }
        )
        # Store full 3D tensor as [y_idx][x_idx][z_idx].
        full_data["amplitude"][step_y][step_x][z_idx] = sample.amplitude_db
        full_data["phase"][step_y][step_x][z_idx] = sample.phase_rad
        full_data["phase_degrees"][step_y][step_x][z_idx] = sample.phase_degrees
        full_data["complex_real"][step_y][step_x][z_idx] = sample.real
        full_data["complex_imag"][step_y][step_x][z_idx] = sample.imag
        if "calibrated_amplitude" in full_data:
            full_data["calibrated_amplitude"][step_y][step_x][
                z_idx
            ] = sample.amplitude_db
            full_data["calibrated_phase"][step_y][step_x][z_idx] = sample.phase_rad
            full_data["calibrated_phase_degrees"][step_y][step_x][
                z_idx
            ] = sample.phase_degrees
            full_data["calibrated_complex_real"][step_y][step_x][z_idx] = sample.real
            full_data["calibrated_complex_imag"][step_y][step_x][z_idx] = sample.imag
        full_data["z_request"][step_y][step_x][z_idx] = z_request
        full_data["z_response"][step_y][step_x][z_idx] = z_response
        full_data["vna_latency_ms"][step_y][step_x][z_idx] = sample.latency_ms
        if sample_tolerance is not None:
            tolerance = abs(float(sample_tolerance))
            late_sample = (
                late_sample
                or abs(z_request - float(z_target)) > tolerance
                or abs(z_response - float(z_target)) > tolerance
            )
        full_data["late_sample"][step_y][step_x][z_idx] = bool(late_sample)
        if late_sample:
            full_data["has_late_samples"] = True
            preview_data["has_late_samples"] = True

        self._emit_preview_data(preview_data)
        self._step_counter += 1
        self._update_progress()
        return True

    def _calibration_enabled(self):
        return (
            self.center_calibration_enabled and self.center_calibration_period_lines > 0
        )

    def _calibration_count_per_angle(self):
        if not self._calibration_enabled():
            return 0
        full_z_lines = len(self.y_range) * len(self.x_range)
        return 1 + int(np.ceil(full_z_lines / self.center_calibration_period_lines))

    def _get_axis_position(self, axis_id):
        try:
            return float(self.runtime.scanner.get_position(axis_id))
        except Exception:
            return None

    def _capture_center_calibration(
        self,
        full_data,
        line_number,
        step_y,
        step_x,
        freq_1,
        freq_2,
        rotation_angle,
    ):
        if not self._calibration_enabled() or not self.runtime.is_measure_running():
            return False

        initial_x = self._get_axis_position(self.runtime.scanner.id_x)
        initial_y = self._get_axis_position(self.runtime.scanner.id_y)
        initial_z = self._get_axis_position(self.runtime.scanner.id_z)

        target_x = (
            self.center_calibration_x
            if self.use_x_sweep or initial_x is None
            else initial_x
        )
        target_y = (
            self.center_calibration_y
            if self.use_y_sweep or initial_y is None
            else initial_y
        )
        target_z = (
            self.center_calibration_z
            if self.use_z_sweep or initial_z is None
            else initial_z
        )

        if self.use_y_sweep and self.runtime.scanner.id_y:
            self.runtime.scanner.move_y(target_y)
            if not self.runtime.is_measure_running():
                return False
            self.msleep(self.y_movement_delay)
        if self.use_x_sweep and self.runtime.scanner.id_x:
            self.runtime.scanner.move_x(target_x)
            if not self.runtime.is_measure_running():
                return False
            self.msleep(self.x_movement_delay)
        if self.use_z_sweep and self.runtime.scanner.id_z:
            self.runtime.scanner.move_z(target_z)
            if not self.runtime.is_measure_running():
                return False
            self.msleep(self.z_movement_delay)

        meas_start = time.time()
        vna_data = self.runtime.vna.get_data()
        meas_duration = time.time() - meas_start
        self._last_vna_latency_s = meas_duration

        sample = build_complex_sample(vna_data, latency_s=meas_duration)
        if sample is None:
            return False
        reference_real = full_data.get("center_calibration", {}).get(
            "reference_complex_real"
        )
        reference_imag = full_data.get("center_calibration", {}).get(
            "reference_complex_imag"
        )
        delta_real = None
        delta_imag = None
        drift_amplitude_ratio = None
        drift_phase_rad = None
        if reference_real is not None and reference_imag is not None:
            reference_complex = complex(float(reference_real), float(reference_imag))
            current_complex = sample.complex_value
            delta = current_complex - reference_complex
            delta_real = float(delta.real)
            delta_imag = float(delta.imag)
            if abs(reference_complex) > 1e-12:
                drift = current_complex / reference_complex
                drift_amplitude_ratio = float(abs(drift))
                drift_phase_rad = float(np.angle(drift))

        calibration_points = full_data.setdefault("calibration_points", [])
        actual_x = self._get_axis_position(self.runtime.scanner.id_x)
        actual_y = self._get_axis_position(self.runtime.scanner.id_y)
        actual_z = self._get_axis_position(self.runtime.scanner.id_z)
        calibration_point = {
            "line_number": int(line_number),
            "after_y_index": None if step_y is None else int(step_y),
            "after_x_index": None if step_x is None else int(step_x),
            "after_y": None if step_y is None else float(self.y_range[step_y]),
            "after_x": None if step_x is None else float(self.x_range[step_x]),
            "requested_target_x": float(self.center_calibration_x),
            "requested_target_y": float(self.center_calibration_y),
            "requested_target_z": float(self.center_calibration_z),
            "target_x": float(target_x),
            "target_y": float(target_y),
            "target_z": float(target_z),
            "actual_x": actual_x,
            "actual_y": actual_y,
            "actual_z": actual_z,
            "x_moved": bool(self.use_x_sweep),
            "y_moved": bool(self.use_y_sweep),
            "z_moved": bool(self.use_z_sweep),
            "freq_1": self._optional_float(freq_1),
            "freq_2": self._optional_float(freq_2),
            "vna_cw_frequency_hz": full_data.get("vna_cw_frequency_hz"),
            "amp_1": full_data.get("amp_1"),
            "amp_2": full_data.get("amp_2"),
            "rotation_angle": float(rotation_angle),
            "complex_real": sample.real,
            "complex_imag": sample.imag,
            "amplitude": sample.amplitude_db,
            "phase": sample.phase_rad,
            "delta_from_reference_real": delta_real,
            "delta_from_reference_imag": delta_imag,
            "drift_amplitude_ratio": drift_amplitude_ratio,
            "drift_phase_rad": drift_phase_rad,
            "vna_latency_ms": sample.latency_ms,
            "elapsed_s": float(time.time() - self._start_time),
        }
        calibration_points.append(calibration_point)
        if line_number == 0:
            full_data["center_calibration"]["reference_complex_real"] = sample.real
            full_data["center_calibration"]["reference_complex_imag"] = sample.imag
            full_data["center_calibration"]["reference_amplitude"] = sample.amplitude_db
            full_data["center_calibration"]["reference_phase"] = sample.phase_rad
        elif step_y is not None and step_x is not None:
            if self.use_y_sweep and self.runtime.scanner.id_y:
                self.runtime.scanner.move_y(float(self.y_range[step_y]))
                if not self.runtime.is_measure_running():
                    return None
                self.msleep(self.y_movement_delay)
            if self.use_x_sweep and self.runtime.scanner.id_x:
                self.runtime.scanner.move_x(float(self.x_range[step_x]))
                if not self.runtime.is_measure_running():
                    return None
                self.msleep(self.x_movement_delay)
        self.log.emit(
            {
                "type": "info",
                "msg": (
                    "Center calibration "
                    f"line={line_number}, X={target_x:.4f}, Y={target_y:.4f}, "
                    f"Z={target_z:.4f}, amp={sample.amplitude_db:.5f} dB, "
                    f"phase={sample.phase_rad:.3f}"
                ),
            }
        )
        self._step_counter += 1
        self._update_progress()
        return calibration_point

    def _line_to_indices(self, line_number):
        line_index = int(line_number) - 1
        x_count = len(self.x_range)
        return line_index // x_count, line_index % x_count

    @staticmethod
    def _calibration_complex(calibration_point):
        return complex(
            float(calibration_point["complex_real"]),
            float(calibration_point["complex_imag"]),
        )

    def _apply_center_calibration_interval(
        self,
        full_data,
        previous_calibration,
        current_calibration,
    ):
        if previous_calibration is None or current_calibration is None:
            return

        start_line = int(previous_calibration["line_number"]) + 1
        end_line = int(current_calibration["line_number"])
        if end_line < start_line:
            return

        reference_real = full_data.get("center_calibration", {}).get(
            "reference_complex_real"
        )
        reference_imag = full_data.get("center_calibration", {}).get(
            "reference_complex_imag"
        )
        if reference_real is None or reference_imag is None:
            return
        if "calibrated_amplitude" not in full_data:
            return

        reference_complex = complex(float(reference_real), float(reference_imag))
        previous_sample = CalibrationSample(
            line_number=int(previous_calibration["line_number"]),
            complex_value=self._calibration_complex(previous_calibration),
        )
        current_sample = CalibrationSample(
            line_number=int(current_calibration["line_number"]),
            complex_value=self._calibration_complex(current_calibration),
        )

        for line_number in range(start_line, end_line + 1):
            step_y, step_x = self._line_to_indices(line_number)
            line_calibration = interpolate_calibration(
                previous_sample,
                current_sample,
                line_number,
            )
            factor = calibration_factor(reference_complex, line_calibration)
            (
                corrected_real,
                corrected_imag,
                corrected_amplitude,
                corrected_phase,
            ) = apply_complex_factor(
                full_data["complex_real"][step_y, step_x, :],
                full_data["complex_imag"][step_y, step_x, :],
                factor,
            )

            full_data["calibrated_complex_real"][step_y, step_x, :] = corrected_real
            full_data["calibrated_complex_imag"][step_y, step_x, :] = corrected_imag
            full_data["calibrated_amplitude"][step_y, step_x, :] = corrected_amplitude
            full_data["calibrated_phase"][step_y, step_x, :] = corrected_phase
            full_data["calibrated_phase_degrees"][step_y, step_x, :] = np.rad2deg(
                corrected_phase,
            ).astype(np.float32, copy=False)

    def _scan_z_fly(self, full_data, preview_data, step_y, step_x, freq_1, freq_2):
        z_targets = np.asarray(self.z_range, dtype=float)
        if z_targets.size == 0:
            return 0

        # Degenerate case: only one point on Z.
        if z_targets.size == 1:
            if self.use_z_sweep:
                self.runtime.scanner.move_z(float(z_targets[0]))
                self.msleep(self.z_movement_delay)
            else:
                self.msleep(self.no_movement_delay)
            return int(
                self._capture_point(
                    full_data,
                    preview_data,
                    step_y,
                    step_x,
                    0,
                    float(z_targets[0]),
                    freq_1,
                    freq_2,
                )
            )

        direction = 1.0 if z_targets[-1] >= z_targets[0] else -1.0
        dz = np.diff(z_targets)
        min_step = float(np.min(np.abs(dz))) if dz.size else 0.0
        tolerance = max(0.05, 0.45 * min_step) if min_step > 0 else 0.05

        start_z = float(z_targets[0])
        end_z = float(z_targets[-1])

        captured = 0
        missed = 0
        late = 0
        target_idx = 0

        if self.use_z_sweep:
            # Between fly passes, keep default (fast) profile.
            self._apply_z_profile(self._z_fast_profile)
            self.runtime.scanner.move_z(start_z)
            self.msleep(self.z_movement_delay)
            if self.auto_adjust_z_fly_speed:
                self._probe_vna_latency()
                self._limit_z_fly_speed_for_latency(min_step, tolerance)
            else:
                self.log.emit(
                    {
                        "type": "info",
                        "msg": (
                            "Z fly auto speed adjust disabled; "
                            f"using requested speed={self.z_fly_speed:.4f}."
                        ),
                    }
                )
            if self._capture_point(
                full_data,
                preview_data,
                step_y,
                step_x,
                target_idx,
                start_z,
                freq_1,
                freq_2,
                sample_tolerance=min_step,
            ):
                captured += 1
                if full_data["late_sample"][step_y][step_x][target_idx]:
                    late += 1
            target_idx += 1
            # During acquisition pass, use requested constant fly speed.
            self._apply_z_profile(self._z_fly_profile)
            self.runtime.scanner.move_z_async(end_z)

        travel = abs(end_z - start_z)
        fly_speed = abs(float(self._z_fly_profile.get("speed", self.z_fly_speed)))
        expected = travel / max(fly_speed, 1e-6)
        timeout_s = max(2.0, expected * 4.0 + 2.0)
        started = time.time()

        while target_idx < z_targets.size:
            if not self.runtime.is_measure_running():
                try:
                    self.runtime.scanner.soft_stop(self.runtime.scanner.id_z)
                except Exception:
                    pass
                break

            current_z = float(
                self.runtime.scanner.get_position(self.runtime.scanner.id_z)
            )
            target_z = float(z_targets[target_idx])
            delta = current_z - target_z

            if abs(delta) <= tolerance:
                if self._capture_point(
                    full_data,
                    preview_data,
                    step_y,
                    step_x,
                    target_idx,
                    target_z,
                    freq_1,
                    freq_2,
                    sample_tolerance=min_step,
                ):
                    captured += 1
                    if full_data["late_sample"][step_y][step_x][target_idx]:
                        late += 1
                target_idx += 1
                continue

            overshoot = (direction > 0 and delta > tolerance) or (
                direction < 0 and delta < -tolerance
            )
            if overshoot:
                if self._capture_point(
                    full_data,
                    preview_data,
                    step_y,
                    step_x,
                    target_idx,
                    target_z,
                    freq_1,
                    freq_2,
                    late_sample=True,
                    sample_tolerance=min_step,
                ):
                    captured += 1
                    if full_data["late_sample"][step_y][step_x][target_idx]:
                        late += 1
                else:
                    missed += 1
                target_idx += 1
                continue

            if time.time() - started > timeout_s:
                self.log.emit(
                    {
                        "type": "warning",
                        "msg": (
                            f"Fly Z timeout at y={step_y}, x={step_x}; "
                            f"captured={captured}, missed={missed}, total={z_targets.size}"
                        ),
                    }
                )
                break

            self.msleep(max(1, int(self.fly_poll_delay_ms)))

        if self.use_z_sweep:
            try:
                self.runtime.scanner.wait_for_stop_z(timeout_s=3.0)
            except Exception as err:
                self.log.emit(
                    {"type": "warning", "msg": f"Z fly stop wait failed: {err}"}
                )
            # Restore fast/default profile for non-acquisition moves.
            self._apply_z_profile(self._z_fast_profile)

        if late > 0 or missed > 0:
            self.log.emit(
                {
                    "type": "warning" if missed > 0 else "info",
                    "msg": (
                        f"Fly Z quality at y={step_y}, x={step_x}: "
                        f"late={late}, missed={missed}, captured={captured}, "
                        f"total={z_targets.size}."
                    ),
                }
            )
        return captured

    def run(self):
        try:
            self._configure_vna()

            plan = build_measurement_plan(self.config)
            freq_points = plan.freq_points
            if self.use_generators:
                self.generator_amps_1 = normalize_amplitudes(
                    self.generator_amps_1,
                    freq_points,
                )
                self.generator_amps_2 = normalize_amplitudes(
                    self.generator_amps_2,
                    freq_points,
                )
            else:
                self.generator_amps_1 = [None]
                self.generator_amps_2 = [None]

            self._total_steps = plan.total_steps
            self._step_counter = 0
            self._start_time = time.time()

            if self.use_z_fly_mode and self.use_z_sweep:
                if float(self.z_fly_speed) <= 0:
                    raise ValueError("Z fly speed must be > 0")
                self._build_z_profiles()

            use_z_snake = self.use_z_snake_pattern and not self.use_z_fly_mode

            if self.use_generators:
                freq_range_1 = np.linspace(
                    self.generator_freq_start_1, self.generator_freq_stop_1, freq_points
                )
                freq_range_2 = np.linspace(
                    self.generator_freq_start_2, self.generator_freq_stop_2, freq_points
                )
            else:
                freq_range_1 = [None]
                freq_range_2 = [None]
            vna_cw_range_hz = self._vna_cw_frequency_range_hz()
            stop_requested = False
            for vna_cw_frequency_hz in vna_cw_range_hz:
                if vna_cw_frequency_hz is not None:
                    self.runtime.vna.set_cw_frequency(vna_cw_frequency_hz)
                    self.log.emit(
                        {
                            "type": "info",
                            "msg": (
                                "VNA CW frequency "
                                f"{vna_cw_frequency_hz / 1e9:.6f} GHz"
                            ),
                        }
                    )
                    time.sleep(0.1)
                for freq_1, amp_1, freq_2, amp_2 in zip(
                    freq_range_1,
                    self.generator_amps_1,
                    freq_range_2,
                    self.generator_amps_2,
                ):
                    if not self.runtime.is_measure_running():
                        stop_requested = True
                        break
                    if self.use_generators:
                        if amp_1 is not None:
                            self.runtime.generator_1.set_power(-100)
                        self.runtime.generator_1.set_frequency(freq_1 * 1e9)
                        if amp_1 is not None:
                            self.runtime.generator_1.set_power(amp_1)
                        if amp_2 is not None:
                            self.runtime.generator_2.set_power(-100)
                        self.runtime.generator_2.set_frequency(freq_2 * 1e9)
                        if amp_2 is not None:
                            self.runtime.generator_2.set_power(amp_2)

                        time.sleep(
                            0.3
                        )  # Allow generators to stabilize before measurement.

                    for rotation_angle in self.rotation_range:
                        if not self.runtime.is_measure_running():
                            stop_requested = True
                            break
                        if self.use_rotation_sweep:
                            current_angle = self.runtime.scanner.get_position(
                                self.runtime.scanner.id_rotation,
                                self.runtime.scanner.rotation_unit,
                            )
                            if not self.runtime.is_measure_running():
                                stop_requested = True
                                break
                            self.runtime.scanner.move_rotation(
                                float(rotation_angle),
                                timeout_s=self._rotation_move_timeout_s(
                                    current_angle,
                                    rotation_angle,
                                ),
                            )
                            if not self.runtime.is_measure_running():
                                stop_requested = True
                                break
                            self.msleep(self.no_movement_delay)
                        if not self.runtime.is_measure_running():
                            stop_requested = True
                            break

                        full_data = create_measurement_block(
                            axes=MeasurementAxes(
                                x=np.asarray(self.x_range, dtype=np.float32),
                                y=np.asarray(self.y_range, dtype=np.float32),
                                z=np.asarray(self.z_range, dtype=np.float32),
                            ),
                            freq_1=freq_1,
                            freq_2=freq_2,
                            amp_1=amp_1,
                            amp_2=amp_2,
                            vna_cw_frequency_hz=vna_cw_frequency_hz,
                            rotation_angle=float(rotation_angle),
                            center_calibration={
                                "enabled": self._calibration_enabled(),
                                "period_lines": self.center_calibration_period_lines,
                                "target_x": self.center_calibration_x,
                                "target_y": self.center_calibration_y,
                                "target_z": self.center_calibration_z,
                                "reference_complex_real": None,
                                "reference_complex_imag": None,
                                "reference_amplitude": None,
                                "reference_phase": None,
                            },
                        )
                        preview_data = create_preview_view(full_data)
                        self.measure.data.append(full_data)
                        angle_has_data = False
                        angle_line_count = 0
                        last_completed_step_y = None
                        last_completed_step_x = None
                        previous_calibration = None
                        if self._calibration_enabled():
                            previous_calibration = self._capture_center_calibration(
                                full_data,
                                0,
                                None,
                                None,
                                freq_1,
                                freq_2,
                                rotation_angle,
                            )
                            if previous_calibration is None:
                                stop_requested = True
                            else:
                                angle_has_data = True
                        if stop_requested:
                            break

                        for step_y, y in enumerate(self.y_range):
                            if not self.runtime.is_measure_running():
                                stop_requested = True
                                break
                            if self.use_y_sweep:
                                self.runtime.scanner.move_y(y)
                                if not self.runtime.is_measure_running():
                                    stop_requested = True
                                    break
                                self.msleep(self.y_movement_delay)
                            if not self.runtime.is_measure_running():
                                stop_requested = True
                                break
                            for step_x, x in enumerate(self.x_range):
                                if not self.runtime.is_measure_running():
                                    stop_requested = True
                                    break
                                if self.use_x_sweep:
                                    self.runtime.scanner.move_x(x)
                                    if not self.runtime.is_measure_running():
                                        stop_requested = True
                                        break
                                    self.msleep(self.x_movement_delay)
                                if not self.runtime.is_measure_running():
                                    stop_requested = True
                                    break

                                line_completed = False
                                if self.use_z_fly_mode and self.use_z_sweep:
                                    captured = self._scan_z_fly(
                                        full_data,
                                        preview_data,
                                        step_y,
                                        step_x,
                                        freq_1,
                                        freq_2,
                                    )
                                    if captured > 0:
                                        angle_has_data = True
                                    if not self.runtime.is_measure_running():
                                        stop_requested = True
                                        break
                                    line_completed = True
                                else:
                                    if use_z_snake:
                                        # Alternate Z direction for each X row in step mode.
                                        if step_x % 2 == 0:
                                            z_indices = range(len(self.z_range))
                                        else:
                                            z_indices = reversed(
                                                range(len(self.z_range))
                                            )
                                    else:
                                        z_indices = range(len(self.z_range))

                                    for z_idx in z_indices:
                                        if not self.runtime.is_measure_running():
                                            stop_requested = True
                                            break
                                        z = self.z_range[z_idx]
                                        if self.use_z_sweep:
                                            self.runtime.scanner.move_z(z)
                                            if not self.runtime.is_measure_running():
                                                stop_requested = True
                                                break
                                            self.msleep(self.z_movement_delay)
                                        else:
                                            self.msleep(self.no_movement_delay)
                                        if not self.runtime.is_measure_running():
                                            stop_requested = True
                                            break

                                        if self._capture_point(
                                            full_data,
                                            preview_data,
                                            step_y,
                                            step_x,
                                            z_idx,
                                            z,
                                            freq_1,
                                            freq_2,
                                        ):
                                            angle_has_data = True
                                        if not self.runtime.is_measure_running():
                                            stop_requested = True
                                            break
                                    if stop_requested:
                                        break
                                    line_completed = True

                                if line_completed:
                                    angle_line_count += 1
                                    last_completed_step_y = step_y
                                    last_completed_step_x = step_x
                                    self._emit_preview_data(preview_data)
                                    if (
                                        self._calibration_enabled()
                                        and angle_line_count
                                        % self.center_calibration_period_lines
                                        == 0
                                    ):
                                        current_calibration = (
                                            self._capture_center_calibration(
                                                full_data,
                                                angle_line_count,
                                                step_y,
                                                step_x,
                                                freq_1,
                                                freq_2,
                                                rotation_angle,
                                            )
                                        )
                                        if current_calibration is not None:
                                            self._apply_center_calibration_interval(
                                                full_data,
                                                previous_calibration,
                                                current_calibration,
                                            )
                                            previous_calibration = current_calibration
                                            self._emit_preview_data(
                                                preview_data,
                                                force=True,
                                            )
                                            angle_has_data = True
                                        if not self.runtime.is_measure_running():
                                            stop_requested = True
                                            break
                            if stop_requested:
                                break

                        if (
                            self._calibration_enabled()
                            and not stop_requested
                            and previous_calibration is not None
                            and last_completed_step_y is not None
                            and int(previous_calibration["line_number"])
                            < angle_line_count
                        ):
                            current_calibration = self._capture_center_calibration(
                                full_data,
                                angle_line_count,
                                last_completed_step_y,
                                last_completed_step_x,
                                freq_1,
                                freq_2,
                                rotation_angle,
                            )
                            if current_calibration is not None:
                                self._apply_center_calibration_interval(
                                    full_data,
                                    previous_calibration,
                                    current_calibration,
                                )
                                self._emit_preview_data(preview_data, force=True)
                                angle_has_data = True
                            if not self.runtime.is_measure_running():
                                stop_requested = True

                        if angle_has_data:
                            self._emit_preview_data(preview_data, force=True)
                            if stop_requested:
                                break
                        if stop_requested:
                            break
                if stop_requested:
                    break

        except (AttributeError, Exception) as e:
            self.log.emit({"type": "error", "msg": f"{e}"})
        finally:
            # Ensure Z profile is restored after fly measurement.
            if self.use_z_fly_mode and self.use_z_sweep:
                self._apply_z_profile(self._z_fast_profile)

        self.measure.save(True)
        self.final_data.emit(self.measure.data)
