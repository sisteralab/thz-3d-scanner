import logging
import time

import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QCheckBox,
    QLineEdit,
)

from interface.ui.Button import Button
from interface.ui.DoubleSpinBox import DoubleSpinBox
from interface.ui.Lines import HLine
from store.data import MeasureModel
from store.state import State
from utils.functions import steps_to_time, convert_seconds


logger = logging.getLogger(__name__)


class MeasureThread(QThread):
    data = Signal(dict)
    final_data = Signal(list)
    progress = Signal(int)
    remaining_time = Signal(str)
    log = Signal(dict)

    def __init__(
        self,
        x_range,
        y_range,
        z_range,
        rotation_range,
        vna_power,
        vna_start,
        vna_stop,
        vna_points,
        generator_freq_start_1,
        generator_freq_stop_1,
        generator_freq_points_1,
        generator_amps_1,
        generator_freq_start_2,
        generator_freq_stop_2,
        generator_freq_points_2,
        generator_amps_2,
        vna_bandwidth=1000,
        vna_average_count=1,
        vna_average_enabled=False,
        use_x_sweep=True,
        use_y_sweep=True,
        use_z_sweep=True,
        use_z_snake_pattern=True,
        use_z_fly_mode=False,
        z_fly_speed=2.0,
        auto_adjust_z_fly_speed=True,
        use_rotation_sweep=False,
        plot_update_hz=10.0,
        x_movement_delay=100,
        y_movement_delay=150,
        z_movement_delay=200,
        no_movement_delay=50,
        fly_poll_delay_ms=5,
    ):
        super().__init__()
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
        self.rotation_range = rotation_range
        self.vna_power = vna_power
        self.vna_start = vna_start
        self.vna_stop = vna_stop
        self.vna_points = vna_points
        self.generator_freq_start_1 = generator_freq_start_1
        self.generator_freq_stop_1 = generator_freq_stop_1
        self.generator_freq_points_1 = generator_freq_points_1
        self.generator_amps_1 = generator_amps_1
        self.generator_freq_start_2 = generator_freq_start_2
        self.generator_freq_stop_2 = generator_freq_stop_2
        self.generator_freq_points_2 = generator_freq_points_2
        self.generator_amps_2 = generator_amps_2
        self.vna_bandwidth = vna_bandwidth
        self.vna_average_count = vna_average_count
        self.vna_average_enabled = vna_average_enabled
        self.use_x_sweep = use_x_sweep
        self.use_y_sweep = use_y_sweep
        self.use_z_sweep = use_z_sweep
        self.use_z_snake_pattern = use_z_snake_pattern
        self.use_z_fly_mode = use_z_fly_mode
        self.z_fly_speed = z_fly_speed
        self.auto_adjust_z_fly_speed = auto_adjust_z_fly_speed
        self.use_rotation_sweep = use_rotation_sweep
        self.plot_update_hz = max(0.01, float(plot_update_hz))
        self._last_preview_emit_time = 0.0
        self.x_movement_delay = x_movement_delay
        self.y_movement_delay = y_movement_delay
        self.z_movement_delay = z_movement_delay
        self.no_movement_delay = no_movement_delay
        self.fly_poll_delay_ms = fly_poll_delay_ms
        self._step_counter = 0
        self._total_steps = 0
        self._start_time = 0.0
        self._z_fast_profile = None
        self._z_fly_profile = None
        self._last_vna_latency_s = 0.0

        self.measure = MeasureModel.objects.create(data=[])
        self.measure.save(False)

    def _preview_emit_interval_s(self):
        update_hz = max(
            0.01,
            float(getattr(State, "plot_update_hz", self.plot_update_hz)),
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
        State.vna.set_parameter("BA")
        try:
            State.vna.set_start_time(self.vna_start)
            State.vna.set_stop_time(self.vna_stop)
        except Exception as err:
            self.log.emit(
                {
                    "type": "warning",
                    "msg": f"Failed to apply VNA start/stop time: {err}",
                }
            )
        State.vna.set_sweep(max(1, int(self.vna_points)))
        State.vna.set_power(self.vna_power)
        State.vna.set_channel_format("COMP")
        State.vna.set_average_count(max(1, int(self.vna_average_count)))
        State.vna.set_average_status(bool(self.vna_average_enabled))
        State.vna.set_bandwidth(max(1, int(self.vna_bandwidth)))

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
        fallback_fast_speed = float(State.scanner_z_speed)
        fallback_fast_accel = float(State.scanner_z_accel)
        fallback_fast_decel = float(State.scanner_z_decel)

        try:
            self._z_fast_profile = State.scanner.get_move_settings(State.scanner.id_z)
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
        State.vna.get_data()
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
            State.scanner.set_move_settings(
                State.scanner.id_z,
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
                z_request = float(State.scanner.get_position(State.scanner.id_z))
            except Exception:
                ...
        m_s_time = time.time()
        vna_data = State.vna.get_data()
        meas_duration = time.time() - m_s_time
        self._last_vna_latency_s = meas_duration
        print(f"Meas time {meas_duration} s")
        z_response = z_request
        if self.use_z_sweep:
            try:
                z_response = float(State.scanner.get_position(State.scanner.id_z))
            except Exception:
                ...
        real = np.asarray(vna_data.get("real", []), dtype=np.float32)
        imag = np.asarray(vna_data.get("imag", []), dtype=np.float32)
        points_count = int(min(real.size, imag.size))
        if points_count == 0:
            return False

        mean_real = float(np.mean(real[:points_count], dtype=np.float64))
        mean_imag = float(np.mean(imag[:points_count], dtype=np.float64))
        dat = float(20 * np.log10(max(np.hypot(mean_real, mean_imag), 1e-12)))
        phase = float(np.arctan2(mean_imag, mean_real))
        self.log.emit(
            {
                "type": "info",
                "msg": (
                    f"freq1 {freq_1:.5f}GHz; freq2 {freq_2:.5f}GHz; "
                    f"pow {dat:.5f} dB; phase {phase:.2f}"
                ),
            }
        )
        # Store full 3D tensor as [y_idx][x_idx][z_idx].
        full_data["amplitude"][step_y][step_x][z_idx] = dat
        full_data["phase"][step_y][step_x][z_idx] = phase
        full_data["complex_real"][step_y][step_x][z_idx] = mean_real
        full_data["complex_imag"][step_y][step_x][z_idx] = mean_imag
        full_data["z_request"][step_y][step_x][z_idx] = z_request
        full_data["z_response"][step_y][step_x][z_idx] = z_response
        full_data["vna_latency_ms"][step_y][step_x][z_idx] = float(
            meas_duration * 1000.0
        )
        if sample_tolerance is not None:
            tolerance = abs(float(sample_tolerance))
            late_sample = (
                late_sample
                or abs(z_request - float(z_target)) > tolerance
                or abs(z_response - float(z_target)) > tolerance
            )
        full_data["late_sample"][step_y][step_x][z_idx] = bool(late_sample)

        # Emit only lightweight data needed by live plots, throttled to avoid GUI backlog.
        self._emit_preview_data(preview_data)

        self._step_counter += 1
        self._update_progress()
        return True

    def _scan_z_fly(self, full_data, preview_data, step_y, step_x, freq_1, freq_2):
        z_targets = np.asarray(self.z_range, dtype=float)
        if z_targets.size == 0:
            return 0

        # Degenerate case: only one point on Z.
        if z_targets.size == 1:
            if self.use_z_sweep:
                State.scanner.move_z(float(z_targets[0]))
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
            State.scanner.move_z(start_z)
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
            State.scanner.move_z_async(end_z)

        travel = abs(end_z - start_z)
        fly_speed = abs(float(self._z_fly_profile.get("speed", self.z_fly_speed)))
        expected = travel / max(fly_speed, 1e-6)
        timeout_s = max(2.0, expected * 4.0 + 2.0)
        started = time.time()

        while target_idx < z_targets.size:
            if not State.measure_running:
                try:
                    State.scanner.soft_stop(State.scanner.id_z)
                except Exception:
                    pass
                break

            current_z = float(State.scanner.get_position(State.scanner.id_z))
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
                State.scanner.wait_for_stop_z(timeout_s=3.0)
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

            freq_points = np.min(
                [self.generator_freq_points_1, self.generator_freq_points_2]
            )

            def _normalize_amps(amps):
                if type(amps) == list:
                    if len(amps) >= freq_points:
                        return amps[:freq_points]
                    if len(amps) >= 1:
                        diff = freq_points - len(amps)
                        amps.extend([amps[-1] for _ in range(diff)])
                        return amps
                return [None for _ in range(freq_points)]

            self.generator_amps_1 = _normalize_amps(self.generator_amps_1)
            self.generator_amps_2 = _normalize_amps(self.generator_amps_2)

            self._total_steps = (
                len(self.rotation_range)
                * len(self.y_range)
                * len(self.x_range)
                * len(self.z_range)
                * freq_points
            )
            self._step_counter = 0
            self._start_time = time.time()

            if self.use_z_fly_mode and self.use_z_sweep:
                if float(self.z_fly_speed) <= 0:
                    raise ValueError("Z fly speed must be > 0")
                self._build_z_profiles()

            use_z_snake = self.use_z_snake_pattern and not self.use_z_fly_mode

            freq_range_1 = np.linspace(
                self.generator_freq_start_1, self.generator_freq_stop_1, freq_points
            )
            freq_range_2 = np.linspace(
                self.generator_freq_start_2, self.generator_freq_stop_2, freq_points
            )
            stop_requested = False
            for freq_1, amp_1, freq_2, amp_2 in zip(
                freq_range_1, self.generator_amps_1, freq_range_2, self.generator_amps_2
            ):
                print(f"AMP 1: {amp_1}")
                if amp_1 is not None:
                    State.generator_1.set_power(-100)
                State.generator_1.set_frequency(freq_1 * 1e9)
                if amp_1 is not None:
                    State.generator_1.set_power(amp_1)
                if amp_2 is not None:
                    State.generator_2.set_power(-100)
                State.generator_2.set_frequency(freq_2 * 1e9)
                if amp_2 is not None:
                    State.generator_2.set_power(amp_2)

                time.sleep(0.3)  # Allow generators to stabilize before measurement.

                for rotation_angle in self.rotation_range:
                    if not State.measure_running:
                        stop_requested = True
                        break
                    if self.use_rotation_sweep:
                        current_angle = State.scanner.get_position(
                            State.scanner.id_rotation,
                            State.scanner.rotation_unit,
                        )
                        if not State.measure_running:
                            stop_requested = True
                            break
                        State.scanner.move_rotation(
                            float(rotation_angle),
                            timeout_s=self._rotation_move_timeout_s(
                                current_angle,
                                rotation_angle,
                            ),
                        )
                        if not State.measure_running:
                            stop_requested = True
                            break
                        self.msleep(self.no_movement_delay)
                        if not State.measure_running:
                            stop_requested = True
                            break

                    full_data = {
                        "freq_1": freq_1,
                        "amp_1": amp_1,
                        "freq_2": freq_2,
                        "amp_2": amp_2,
                        "rotation_angle": float(rotation_angle),
                        "x": self.x_range.tolist(),
                        "y": self.y_range.tolist(),
                        "z": self.z_range.tolist(),
                        "amplitude": np.zeros(
                            (len(self.y_range), len(self.x_range), len(self.z_range))
                        ).tolist(),
                        "phase": np.zeros(
                            (len(self.y_range), len(self.x_range), len(self.z_range))
                        ).tolist(),
                        "complex_real": np.zeros(
                            (len(self.y_range), len(self.x_range), len(self.z_range))
                        ).tolist(),
                        "complex_imag": np.zeros(
                            (len(self.y_range), len(self.x_range), len(self.z_range))
                        ).tolist(),
                        "z_request": np.zeros(
                            (len(self.y_range), len(self.x_range), len(self.z_range))
                        ).tolist(),
                        "z_response": np.zeros(
                            (len(self.y_range), len(self.x_range), len(self.z_range))
                        ).tolist(),
                        "late_sample": np.zeros(
                            (len(self.y_range), len(self.x_range), len(self.z_range)),
                            dtype=bool,
                        ).tolist(),
                        "vna_latency_ms": np.zeros(
                            (len(self.y_range), len(self.x_range), len(self.z_range))
                        ).tolist(),
                    }
                    preview_data = {
                        "freq_1": freq_1,
                        "amp_1": amp_1,
                        "freq_2": freq_2,
                        "amp_2": amp_2,
                        "rotation_angle": full_data["rotation_angle"],
                        "x": full_data["x"],
                        "y": full_data["y"],
                        "z": full_data["z"],
                        "amplitude": full_data["amplitude"],
                        "phase": full_data["phase"],
                        "complex_real": full_data["complex_real"],
                        "complex_imag": full_data["complex_imag"],
                        "z_request": full_data["z_request"],
                        "z_response": full_data["z_response"],
                        "late_sample": full_data["late_sample"],
                        "vna_latency_ms": full_data["vna_latency_ms"],
                    }
                    angle_has_data = False

                    for step_y, y in enumerate(self.y_range):
                        if not State.measure_running:
                            stop_requested = True
                            break
                        if self.use_y_sweep:
                            State.scanner.move_y(y)
                            if not State.measure_running:
                                stop_requested = True
                                break
                            self.msleep(self.y_movement_delay)
                        if not State.measure_running:
                            stop_requested = True
                            break
                        for step_x, x in enumerate(self.x_range):
                            if not State.measure_running:
                                stop_requested = True
                                break
                            if self.use_x_sweep:
                                State.scanner.move_x(x)
                                if not State.measure_running:
                                    stop_requested = True
                                    break
                                self.msleep(self.x_movement_delay)
                            if not State.measure_running:
                                stop_requested = True
                                break

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
                                if not State.measure_running:
                                    stop_requested = True
                                    break
                            else:
                                if use_z_snake:
                                    # Alternate Z direction for each X row in step mode.
                                    if step_x % 2 == 0:
                                        z_indices = range(len(self.z_range))
                                    else:
                                        z_indices = reversed(range(len(self.z_range)))
                                else:
                                    z_indices = range(len(self.z_range))

                                for z_idx in z_indices:
                                    if not State.measure_running:
                                        stop_requested = True
                                        break
                                    z = self.z_range[z_idx]
                                    if self.use_z_sweep:
                                        State.scanner.move_z(z)
                                        if not State.measure_running:
                                            stop_requested = True
                                            break
                                        self.msleep(self.z_movement_delay)
                                    else:
                                        self.msleep(self.no_movement_delay)
                                    if not State.measure_running:
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
                                    if not State.measure_running:
                                        stop_requested = True
                                        break
                                if stop_requested:
                                    break
                        if stop_requested:
                            break

                    if angle_has_data:
                        self._emit_preview_data(preview_data, force=True)
                        self.measure.data.append(full_data)
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

        self.final_data.emit(self.measure.data)
        self.measure.save(True)
        self.finished.emit()


class MeasureWidget(QGroupBox):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle("Measure")

        self.measure_thread = None

        layout = QVBoxLayout()
        g_layout = QGridLayout()
        f_layout = QFormLayout()
        h_layout = QHBoxLayout()

        self.x_check = QCheckBox("X", self)
        self.x_check.setChecked(State.use_x_sweep)
        self.x_start = DoubleSpinBox(self)
        self.x_start.setRange(-1000, 1000)
        self.x_start.setValue(State.x_start)
        self.x_start.valueChanged.connect(self.update_x_step)
        self.x_stop = DoubleSpinBox(self)
        self.x_stop.setRange(-1000, 1000)
        self.x_stop.setValue(State.x_stop)
        self.x_stop.valueChanged.connect(self.update_x_step)
        self.x_points = QSpinBox(self)
        self.x_points.setRange(1, 5000)
        self.x_points.setValue(State.x_points)
        self.x_points.valueChanged.connect(self.update_x_step)
        self.x_points.valueChanged.connect(self.update_approx_time)
        self.x_step = QDoubleSpinBox(self)
        self.x_step.setRange(0.02, 100)
        self.x_step.setSingleStep(0.0125)
        self.x_step.setValue(State.x_step)
        self.x_step.valueChanged.connect(self.update_x_points)

        self.y_check = QCheckBox("Y", self)
        self.y_check.setChecked(State.use_y_sweep)
        self.y_start = DoubleSpinBox(self)
        self.y_start.setRange(-1000, 1000)
        self.y_start.setValue(State.y_start)
        self.y_start.valueChanged.connect(self.update_y_step)
        self.y_stop = DoubleSpinBox(self)
        self.y_stop.setRange(-1000, 1000)
        self.y_stop.setValue(State.y_stop)
        self.y_stop.valueChanged.connect(self.update_y_step)
        self.y_points = QSpinBox(self)
        self.y_points.setRange(1, 5000)
        self.y_points.setValue(State.y_points)
        self.y_points.valueChanged.connect(self.update_y_step)
        self.y_points.valueChanged.connect(self.update_approx_time)
        self.y_step = QDoubleSpinBox(self)
        self.y_step.setRange(0.02, 100)
        self.y_step.setSingleStep(0.0125)
        self.y_step.setValue(State.y_step)
        self.y_step.valueChanged.connect(self.update_y_points)

        self.z_check = QCheckBox("Z", self)
        self.z_check.setChecked(State.use_z_sweep)
        self.z_start = DoubleSpinBox(self)
        self.z_start.setRange(-1000, 1000)
        self.z_start.setValue(State.z_start)
        self.z_start.valueChanged.connect(self.update_z_step)
        self.z_stop = DoubleSpinBox(self)
        self.z_stop.setRange(-1000, 1000)
        self.z_stop.setValue(State.z_stop)
        self.z_stop.valueChanged.connect(self.update_z_step)
        self.z_points = QSpinBox(self)
        self.z_points.setRange(1, 5000)
        self.z_points.setValue(State.z_points)
        self.z_points.valueChanged.connect(self.update_z_step)
        self.z_points.valueChanged.connect(self.update_approx_time)
        self.z_step = QDoubleSpinBox(self)
        self.z_step.setRange(0.02, 100)
        self.z_step.setSingleStep(0.0125)
        self.z_step.setValue(State.z_step)
        self.z_step.valueChanged.connect(self.update_z_points)

        self.rotation_check = QCheckBox("Rotation", self)
        self.rotation_check.setChecked(State.use_rotation_sweep)
        self.rotation_check.toggled.connect(self.update_approx_time)
        self.rotation_start = DoubleSpinBox(self)
        self.rotation_start.setRange(-36000, 36000)
        self.rotation_start.setDecimals(3)
        self.rotation_start.setValue(State.rotation_start)
        self.rotation_start.valueChanged.connect(self.update_rotation_step)
        self.rotation_stop = DoubleSpinBox(self)
        self.rotation_stop.setRange(-36000, 36000)
        self.rotation_stop.setDecimals(3)
        self.rotation_stop.setValue(State.rotation_stop)
        self.rotation_stop.valueChanged.connect(self.update_rotation_step)
        self.rotation_points = QSpinBox(self)
        self.rotation_points.setRange(1, 10000)
        self.rotation_points.setValue(State.rotation_points)
        self.rotation_points.valueChanged.connect(self.update_rotation_step)
        self.rotation_points.valueChanged.connect(self.update_approx_time)
        self.rotation_step = QDoubleSpinBox(self)
        self.rotation_step.setRange(0.001, 36000)
        self.rotation_step.setDecimals(3)
        self.rotation_step.setValue(State.rotation_step)
        self.rotation_step.valueChanged.connect(self.update_rotation_points)

        self.z_snake_check = QCheckBox("Z Snake", self)
        self.z_snake_check.setChecked(State.use_z_snake_pattern)
        self.z_snake_check.setToolTip(
            "Enable snake pattern for Z-axis movement to reduce travel time"
        )
        self.z_fly_check = QCheckBox("Z Fly", self)
        self.z_fly_check.setChecked(State.use_z_fly_mode)
        self.z_fly_check.setToolTip(
            "Move Z continuously with fixed speed and sample VNA while moving"
        )
        self.z_fly_check.toggled.connect(self.on_z_fly_toggled)
        self.auto_adjust_z_fly_speed_check = QCheckBox("Auto Z fly speed", self)
        self.auto_adjust_z_fly_speed_check.setChecked(State.auto_adjust_z_fly_speed)
        self.auto_adjust_z_fly_speed_check.setToolTip(
            "Limit Z Fly speed automatically using measured VNA latency"
        )
        self.z_fly_speed = DoubleSpinBox(self)
        self.z_fly_speed.setRange(0.01, 1000)
        self.z_fly_speed.setDecimals(4)
        self.z_fly_speed.setValue(State.z_fly_speed)

        self.vna_points = QSpinBox(self)
        self.vna_points.setRange(1, 5000)
        self.vna_points.setValue(State.measure_vna_points)
        self.vna_start_time = DoubleSpinBox(self)
        self.vna_start_time.setRange(0, 1e6)
        self.vna_start_time.setDecimals(6)
        self.vna_start_time.setValue(State.measure_vna_start_time)
        self.vna_stop_time = DoubleSpinBox(self)
        self.vna_stop_time.setRange(0, 1e6)
        self.vna_stop_time.setDecimals(6)
        self.vna_stop_time.setValue(State.measure_vna_stop_time)

        self.vna_bandwidth = QSpinBox(self)
        self.vna_bandwidth.setRange(1, 1_000_000)
        self.vna_bandwidth.setSingleStep(100)
        self.vna_bandwidth.setValue(State.measure_vna_bandwidth)

        self.vna_average_enabled = QCheckBox(self)
        self.vna_average_enabled.setChecked(State.measure_vna_average_enabled)
        self.vna_average_count = QSpinBox(self)
        self.vna_average_count.setRange(1, 1024)
        self.vna_average_count.setValue(State.measure_vna_average_count)
        self.vna_average_enabled.toggled.connect(self.vna_average_count.setEnabled)
        self.vna_average_count.setEnabled(self.vna_average_enabled.isChecked())

        self.plot_update_hz = QDoubleSpinBox(self)
        self.plot_update_hz.setRange(0.01, 60.0)
        self.plot_update_hz.setDecimals(2)
        self.plot_update_hz.setSingleStep(0.25)
        self.plot_update_hz.setValue(State.plot_update_hz)
        self.plot_update_hz.setToolTip("How often live amplitude/phase images update")
        self.plot_update_hz.valueChanged.connect(self.on_plot_update_hz_changed)

        self.generator_freq_start_1 = DoubleSpinBox(self)
        self.generator_freq_start_1.setRange(1, 1000)
        self.generator_freq_start_1.setDecimals(5)
        self.generator_freq_start_1.setValue(State.generator_freq_start_1)

        self.generator_freq_stop_1 = DoubleSpinBox(self)
        self.generator_freq_stop_1.setRange(1, 1000)
        self.generator_freq_stop_1.setDecimals(5)
        self.generator_freq_stop_1.setValue(State.generator_freq_stop_1)

        self.generator_freq_points_1 = QSpinBox(self)
        self.generator_freq_points_1.setRange(1, 10000)
        self.generator_freq_points_1.setValue(State.generator_freq_points_1)
        self.generator_freq_points_1.valueChanged.connect(self.update_approx_time)

        self.generator_amps_1 = QLineEdit(self)
        self.generator_amps_1.setText(State.generator_amps_1)

        self.generator_freq_start_2 = DoubleSpinBox(self)
        self.generator_freq_start_2.setRange(1, 1000)
        self.generator_freq_start_2.setDecimals(5)
        self.generator_freq_start_2.setValue(State.generator_freq_start_2)

        self.generator_freq_stop_2 = DoubleSpinBox(self)
        self.generator_freq_stop_2.setRange(1, 1000)
        self.generator_freq_stop_2.setDecimals(5)
        self.generator_freq_stop_2.setValue(State.generator_freq_stop_2)

        self.generator_freq_points_2 = QSpinBox(self)
        self.generator_freq_points_2.setRange(1, 10000)
        self.generator_freq_points_2.setValue(State.generator_freq_points_2)
        self.generator_freq_points_2.valueChanged.connect(self.update_approx_time)
        self.generator_amps_2 = QLineEdit(self)
        self.generator_amps_2.setText(State.generator_amps_2)

        self.approx_time = QLabel("Approx time ~ None", self)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)

        self.btn_start_measure = Button("Start", self, animate=True)
        self.btn_start_measure.clicked.connect(self.start_measure)

        self.btn_stop_measure = Button("Stop", self)
        self.btn_stop_measure.clicked.connect(self.stop_measure)
        self.btn_stop_measure.set_enabled(False)

        g_layout.addWidget(
            QLabel("Axis", self), 0, 0, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(
            QLabel("Start", self), 0, 1, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(
            QLabel("Stop", self), 0, 2, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(
            QLabel("Points", self), 0, 3, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(
            QLabel("Step", self), 0, 4, alignment=Qt.AlignmentFlag.AlignLeft
        )

        g_layout.addWidget(self.x_check, 1, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.x_start, 1, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.x_stop, 1, 2, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.x_points, 1, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.x_step, 1, 4, alignment=Qt.AlignmentFlag.AlignLeft)

        g_layout.addWidget(self.y_check, 2, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.y_start, 2, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.y_stop, 2, 2, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.y_points, 2, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.y_step, 2, 4, alignment=Qt.AlignmentFlag.AlignLeft)

        g_layout.addWidget(self.z_check, 3, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.z_start, 3, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.z_stop, 3, 2, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.z_points, 3, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(self.z_step, 3, 4, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(
            self.rotation_check, 4, 0, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(
            self.rotation_start, 4, 1, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(
            self.rotation_stop, 4, 2, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(
            self.rotation_points, 4, 3, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(
            self.rotation_step, 4, 4, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(
            self.z_snake_check, 5, 0, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(self.z_fly_check, 5, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(
            QLabel("Z fly speed", self), 5, 2, alignment=Qt.AlignmentFlag.AlignLeft
        )
        g_layout.addWidget(self.z_fly_speed, 5, 3, alignment=Qt.AlignmentFlag.AlignLeft)
        g_layout.addWidget(
            self.auto_adjust_z_fly_speed_check,
            5,
            4,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        f_layout.addRow("VNA points", self.vna_points)
        f_layout.addRow("VNA start time, s", self.vna_start_time)
        f_layout.addRow("VNA stop time, s", self.vna_stop_time)
        f_layout.addRow("VNA bandwidth, Hz", self.vna_bandwidth)
        f_layout.addRow("VNA average", self.vna_average_enabled)
        f_layout.addRow("VNA average count", self.vna_average_count)
        f_layout.addRow("Plot update, Hz", self.plot_update_hz)

        f_layout.addRow(HLine(self))

        f_layout.addRow("Generator start 1, GHz", self.generator_freq_start_1)
        f_layout.addRow("Generator stop 1, GHz", self.generator_freq_stop_1)
        f_layout.addRow("Generator points 1", self.generator_freq_points_1)
        f_layout.addRow("Generator amps 1", self.generator_amps_1)

        f_layout.addRow(HLine(self))

        f_layout.addRow("Generator start 2, GHz", self.generator_freq_start_2)
        f_layout.addRow("Generator stop 2, GHz", self.generator_freq_stop_2)
        f_layout.addRow("Generator points 2", self.generator_freq_points_2)
        f_layout.addRow("Generator amps 2", self.generator_amps_2)

        f_layout.addRow(HLine(self))

        f_layout.addRow(self.approx_time)
        f_layout.addRow(self.progress_bar)

        h_layout.addWidget(self.btn_start_measure)
        h_layout.addWidget(self.btn_stop_measure)

        g_layout.setAlignment(Qt.AlignTop)
        f_layout.setAlignment(Qt.AlignBottom)

        layout.addLayout(g_layout)
        layout.addStretch()
        layout.addLayout(f_layout)
        layout.addLayout(h_layout)
        self.setLayout(layout)

        self.run_init_methods()

    def run_init_methods(self):
        self.update_x_step()
        self.update_y_step()
        self.update_z_step()
        self.update_rotation_step()
        self.on_z_fly_toggled(self.z_fly_check.isChecked())
        self.update_approx_time()

    def on_z_fly_toggled(self, enabled):
        self.z_fly_speed.setEnabled(enabled)
        self.auto_adjust_z_fly_speed_check.setEnabled(enabled)
        if enabled:
            self.z_snake_check.setChecked(False)
            self.z_snake_check.setEnabled(False)
        else:
            self.z_snake_check.setEnabled(True)

    @staticmethod
    def on_plot_update_hz_changed(value):
        State.plot_update_hz = float(value)

    def start_measure(self):
        if not State.scanner:
            logger.warning("Scanner is not initialized!")
            return
        if self.x_check.isChecked() and not State.scanner.id_x:
            logger.warning("X sweep is enabled, but X axis is not initialized!")
            return
        if self.y_check.isChecked() and not State.scanner.id_y:
            logger.warning("Y sweep is enabled, but Y axis is not initialized!")
            return
        if self.z_check.isChecked() and not State.scanner.id_z:
            logger.warning("Z sweep is enabled, but Z axis is not initialized!")
            return
        if self.rotation_check.isChecked() and not State.scanner.id_rotation:
            logger.warning(
                "Rotation sweep is enabled, but rotation axis is not initialized!"
            )
            return
        if self.generator_freq_points_2.value() != self.generator_freq_points_1.value():
            logger.warning("Frequency points must be equal!")
            return
        if self.vna_stop_time.value() <= self.vna_start_time.value():
            logger.warning("VNA stop time must be greater than start time!")
            return
        if self.z_fly_check.isChecked() and not self.z_check.isChecked():
            logger.warning("Z Fly mode requires Z sweep enabled!")
            return
        if self.z_fly_check.isChecked() and self.z_fly_speed.value() <= 0:
            logger.warning("Z Fly speed must be > 0!")
            return

        State.generator_freq_start_1 = self.generator_freq_start_1.value()
        State.generator_freq_stop_1 = self.generator_freq_stop_1.value()
        State.generator_freq_points_1 = self.generator_freq_points_1.value()
        State.generator_amps_1 = self.generator_amps_1.text()
        State.generator_freq_start_2 = self.generator_freq_start_2.value()
        State.generator_freq_stop_2 = self.generator_freq_stop_2.value()
        State.generator_freq_points_2 = self.generator_freq_points_2.value()
        State.generator_amps_2 = self.generator_amps_2.text()

        State.use_x_sweep = self.x_check.isChecked()
        State.use_y_sweep = self.y_check.isChecked()
        State.use_z_sweep = self.z_check.isChecked()
        State.use_z_snake_pattern = self.z_snake_check.isChecked()
        State.use_z_fly_mode = self.z_fly_check.isChecked()
        State.z_fly_speed = self.z_fly_speed.value()
        State.auto_adjust_z_fly_speed = self.auto_adjust_z_fly_speed_check.isChecked()
        State.use_rotation_sweep = self.rotation_check.isChecked()
        State.measure_vna_points = self.vna_points.value()
        State.measure_vna_start_time = self.vna_start_time.value()
        State.measure_vna_stop_time = self.vna_stop_time.value()
        State.measure_vna_bandwidth = self.vna_bandwidth.value()
        State.measure_vna_average_enabled = self.vna_average_enabled.isChecked()
        State.measure_vna_average_count = self.vna_average_count.value()
        State.plot_update_hz = self.plot_update_hz.value()

        State.x_start = self.x_start.value()
        State.x_stop = self.x_stop.value()
        State.x_points = self.x_points.value()
        State.x_step = self.x_step.value()
        State.y_start = self.y_start.value()
        State.y_stop = self.y_stop.value()
        State.y_points = self.y_points.value()
        State.y_step = self.y_step.value()
        State.z_start = self.z_start.value()
        State.z_stop = self.z_stop.value()
        State.z_points = self.z_points.value()
        State.z_step = self.z_step.value()
        State.rotation_start = self.rotation_start.value()
        State.rotation_stop = self.rotation_stop.value()
        State.rotation_points = self.rotation_points.value()
        State.rotation_step = self.rotation_step.value()

        amps_1 = []
        raw_amps_1 = self.generator_amps_1.text().replace(" ", "").split(",")
        for a in raw_amps_1:
            try:
                a = float(a)
                amps_1.append(a)
            except ValueError:
                ...
        amps_2 = []
        raw_amps_2 = self.generator_amps_2.text().replace(" ", "").split(",")
        for a in raw_amps_2:
            try:
                a = float(a)
                amps_2.append(a)
            except ValueError:
                ...

        self.measure_thread = MeasureThread(
            x_range=np.linspace(
                self.x_start.value(), self.x_stop.value(), self.x_points.value()
            )
            if self.x_check.isChecked()
            else np.array([0]),
            y_range=np.linspace(
                self.y_start.value(), self.y_stop.value(), self.y_points.value()
            )
            if self.y_check.isChecked()
            else np.array([0]),
            z_range=np.linspace(
                self.z_start.value(), self.z_stop.value(), self.z_points.value()
            )
            if self.z_check.isChecked()
            else np.array([0]),
            rotation_range=np.linspace(
                self.rotation_start.value(),
                self.rotation_stop.value(),
                self.rotation_points.value(),
            )
            if self.rotation_check.isChecked()
            else np.array([0]),
            vna_power=-30,
            vna_start=State.measure_vna_start_time,
            vna_stop=State.measure_vna_stop_time,
            vna_points=State.measure_vna_points,
            generator_freq_start_1=self.generator_freq_start_1.value(),
            generator_freq_stop_1=self.generator_freq_stop_1.value(),
            generator_freq_points_1=self.generator_freq_points_1.value(),
            generator_amps_1=amps_1,
            generator_freq_start_2=self.generator_freq_start_2.value(),
            generator_freq_stop_2=self.generator_freq_stop_2.value(),
            generator_freq_points_2=self.generator_freq_points_2.value(),
            generator_amps_2=amps_2,
            vna_bandwidth=State.measure_vna_bandwidth,
            vna_average_count=State.measure_vna_average_count,
            vna_average_enabled=State.measure_vna_average_enabled,
            use_x_sweep=self.x_check.isChecked(),
            use_y_sweep=self.y_check.isChecked(),
            use_z_sweep=self.z_check.isChecked(),
            use_z_snake_pattern=self.z_snake_check.isChecked(),
            use_z_fly_mode=self.z_fly_check.isChecked(),
            z_fly_speed=self.z_fly_speed.value(),
            auto_adjust_z_fly_speed=self.auto_adjust_z_fly_speed_check.isChecked(),
            use_rotation_sweep=self.rotation_check.isChecked(),
            plot_update_hz=State.plot_update_hz,
            x_movement_delay=State.x_movement_delay,
            y_movement_delay=State.y_movement_delay,
            z_movement_delay=State.z_movement_delay,
            no_movement_delay=State.no_movement_delay,
            fly_poll_delay_ms=max(1, int(min(50, State.no_movement_delay // 5 or 1))),
        )

        update_plot = (
            self.parent()
            .parent()
            .parent()
            .parent()
            .parent()
            .parent()
            .parent()
            .parent()
            .update_plot
        )
        self.measure_thread.data.connect(update_plot)  # FIXME: fix parents later
        self.measure_thread.final_data.connect(update_plot)
        self.measure_thread.progress.connect(lambda x: self.progress_bar.setValue(x))
        self.measure_thread.remaining_time.connect(
            lambda x: self.approx_time.setText(x)
        )
        self.measure_thread.finished.connect(
            lambda: self.btn_start_measure.set_enabled(True)
        )
        self.measure_thread.finished.connect(
            lambda: self.btn_stop_measure.set_enabled(False)
        )
        self.measure_thread.finished.connect(lambda: self.progress_bar.setValue(0))
        self.measure_thread.log.connect(self.set_log)

        State.measure_running = True
        self.measure_thread.start()
        self.btn_start_measure.set_enabled(False)
        self.btn_stop_measure.set_enabled(True)

    def stop_measure(self):
        reply = QMessageBox.question(
            self,
            "Остановка измерение",
            "Уверены, что хотите остановить измерние, продолжить?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            State.measure_running = False
            if State.scanner:
                try:
                    State.scanner.soft_stop_all()
                except Exception as err:
                    logger.warning(f"Failed to stop scanner axes: {err}")

    def update_x_step(self):
        step = (
            np.abs(self.x_stop.value() - self.x_start.value()) / self.x_points.value()
        )
        self.x_step.valueChanged.disconnect(self.update_x_points)
        self.x_step.setValue(step)
        self.x_step.valueChanged.connect(self.update_x_points)

    def update_x_points(self):
        points = (
            np.abs(self.x_stop.value() - self.x_start.value()) / self.x_step.value()
        )
        self.x_points.valueChanged.disconnect(self.update_x_step)
        self.x_points.setValue(points)
        self.x_points.valueChanged.connect(self.update_x_step)

    def update_y_step(self):
        step = (
            np.abs(self.y_stop.value() - self.y_start.value()) / self.y_points.value()
        )
        self.y_step.valueChanged.disconnect(self.update_y_points)
        self.y_step.setValue(step)
        self.y_step.valueChanged.connect(self.update_y_points)

    def update_y_points(self):
        points = (
            np.abs(self.y_stop.value() - self.y_start.value()) / self.y_step.value()
        )
        self.y_points.valueChanged.disconnect(self.update_y_step)
        self.y_points.setValue(points)
        self.y_points.valueChanged.connect(self.update_y_step)

    def update_z_step(self):
        step = (
            np.abs(self.z_stop.value() - self.z_start.value()) / self.z_points.value()
        )
        self.z_step.valueChanged.disconnect(self.update_z_points)
        self.z_step.setValue(step)
        self.z_step.valueChanged.connect(self.update_z_points)

    def update_z_points(self):
        points = (
            np.abs(self.z_stop.value() - self.z_start.value()) / self.z_step.value()
        )
        self.z_points.valueChanged.disconnect(self.update_z_step)
        self.z_points.setValue(points)
        self.z_points.valueChanged.connect(self.update_z_step)

    def update_rotation_step(self):
        step = (
            np.abs(self.rotation_stop.value() - self.rotation_start.value())
            / self.rotation_points.value()
        )
        self.rotation_step.valueChanged.disconnect(self.update_rotation_points)
        self.rotation_step.setValue(step)
        self.rotation_step.valueChanged.connect(self.update_rotation_points)

    def update_rotation_points(self):
        points = (
            np.abs(self.rotation_stop.value() - self.rotation_start.value())
            / self.rotation_step.value()
        )
        self.rotation_points.valueChanged.disconnect(self.update_rotation_step)
        self.rotation_points.setValue(max(1, int(round(points))))
        self.rotation_points.valueChanged.connect(self.update_rotation_step)

    def update_approx_time(self):
        rotation_points = (
            self.rotation_points.value() if self.rotation_check.isChecked() else 1
        )
        steps = (
            rotation_points
            * self.x_points.value()
            * self.y_points.value()
            * self.z_points.value()
            * np.min(
                [
                    self.generator_freq_points_1.value(),
                    self.generator_freq_points_2.value(),
                ]
            )
        )
        self.approx_time.setText(f"Approx time ~ {steps_to_time(steps)}")

    @staticmethod
    def set_log(log: dict):
        log_type = log.get("type")
        if not log_type:
            return
        method = getattr(logger, log_type, None)
        if not method:
            return
        method(log.get("msg"))
