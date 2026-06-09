import logging
import time

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QLabel,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from api.vna import VNA_PARAMETER_OPTIONS, normalize_vna_parameter
from interface.ui.Button import Button
from interface.ui.DoubleSpinBox import DoubleSpinBox
from store.state import State


logger = logging.getLogger(__name__)


class RotationMeasureThread(QThread):
    point = Signal(dict)
    finished_data = Signal(dict)
    progress = Signal(int)
    log = Signal(dict)

    def __init__(
        self,
        angles,
        delay_ms: int,
        vna_points: int,
        vna_bandwidth: int,
        vna_power: float,
        vna_parameter: str,
        vna_output_enabled: bool,
        fly_mode: bool,
        fly_speed: float,
        fly_poll_delay_ms: int = 5,
    ):
        super().__init__()
        self.angles = np.asarray(angles, dtype=float)
        self.delay_ms = int(delay_ms)
        self.vna_points = int(vna_points)
        self.vna_bandwidth = int(vna_bandwidth)
        self.vna_power = float(vna_power)
        self.vna_parameter = str(vna_parameter)
        self.vna_output_enabled = bool(vna_output_enabled)
        self.fly_mode = bool(fly_mode)
        self.fly_speed = float(fly_speed)
        self.fly_poll_delay_ms = int(fly_poll_delay_ms)
        self._rotation_fast_profile = None
        self._rotation_fly_profile = None
        self._running = True

    def request_stop(self):
        self._running = False

    def _configure_vna(self):
        State.vna.set_parameter(self.vna_parameter)
        State.vna.set_sweep(max(1, self.vna_points))
        State.vna.set_power(self.vna_power)
        State.vna.set_output_state(self.vna_output_enabled)
        State.vna.set_channel_format("COMP")
        State.vna.set_average_count(1)
        State.vna.set_average_status(False)
        State.vna.set_bandwidth(max(1, self.vna_bandwidth))

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

    def _build_rotation_profiles(self):
        fallback_fast_speed = float(State.scanner_rotation_speed)
        fallback_fast_accel = float(State.scanner_rotation_accel)
        fallback_fast_decel = float(State.scanner_rotation_decel)
        try:
            self._rotation_fast_profile = State.scanner.get_move_settings(
                State.scanner.id_rotation,
                State.scanner.rotation_unit,
            )
        except Exception:
            self._rotation_fast_profile = None

        if not self._rotation_fast_profile:
            self._rotation_fast_profile = {
                "speed": fallback_fast_speed,
                "accel": fallback_fast_accel,
                "decel": fallback_fast_decel,
            }
            self.log.emit(
                {
                    "type": "warning",
                    "msg": (
                        "Could not read default rotation move profile; "
                        "using Scanner Init rotation move profile."
                    ),
                }
            )

        fly_accel = max(1.0, self.fly_speed / 0.8)
        self._rotation_fly_profile = {
            "speed": self.fly_speed,
            "accel": fly_accel,
            "decel": fly_accel,
        }

    def _apply_rotation_profile(self, profile):
        if not profile:
            return
        State.scanner.set_move_settings(
            State.scanner.id_rotation,
            float(profile["speed"]),
            float(profile["accel"]),
            float(profile["decel"]),
            State.scanner.rotation_unit,
        )

    @staticmethod
    def _extract_point(vna_data):
        real = np.asarray(vna_data.get("real", []), dtype=np.float32)
        imag = np.asarray(vna_data.get("imag", []), dtype=np.float32)
        points_count = int(min(real.size, imag.size))
        if points_count == 0:
            return None

        mean_real = float(np.mean(real[:points_count], dtype=np.float64))
        mean_imag = float(np.mean(imag[:points_count], dtype=np.float64))
        amplitude = float(20 * np.log10(max(np.hypot(mean_real, mean_imag), 1e-12)))
        phase = float(np.arctan2(mean_imag, mean_real))
        return amplitude, phase, mean_real, mean_imag

    def _capture_at_angle(self, angle, result):
        started = time.time()
        vna_data = State.vna.get_data()
        latency_ms = float((time.time() - started) * 1000.0)
        parsed = self._extract_point(vna_data)
        if parsed is None:
            self.log.emit(
                {
                    "type": "warning",
                    "msg": f"No VNA data at angle {angle:.3f} deg",
                }
            )
            return False

        amplitude, phase, mean_real, mean_imag = parsed
        point = {
            "angle": float(angle),
            "amplitude": amplitude,
            "phase": phase,
            "complex_real": mean_real,
            "complex_imag": mean_imag,
            "vna_latency_ms": latency_ms,
        }
        for key, value in point.items():
            result[key].append(value)

        self.point.emit(point)
        return True

    def _rotation_move_timeout_s(self, start_angle, target_angle, speed=None):
        travel = abs(float(target_angle) - float(start_angle))
        speed = abs(float(speed if speed is not None else self.fly_speed))
        return max(5.0, travel / max(speed, 1e-6) * 4.0 + 5.0)

    def _run_step_mode(self, result):
        total = max(1, self.angles.size)
        for index, angle in enumerate(self.angles, start=1):
            if not self._running:
                break

            current_angle = State.scanner.get_position(
                State.scanner.id_rotation,
                State.scanner.rotation_unit,
            )
            State.scanner.move_rotation(
                float(angle),
                timeout_s=self._rotation_move_timeout_s(current_angle, angle),
            )
            self.msleep(max(0, self.delay_ms))

            if self._capture_at_angle(float(angle), result):
                self.progress.emit(int(round(index * 100 / total)))

    def _run_fly_mode(self, result):
        if self.angles.size == 0:
            return
        if self.angles.size == 1:
            current_angle = State.scanner.get_position(
                State.scanner.id_rotation,
                State.scanner.rotation_unit,
            )
            State.scanner.move_rotation(
                float(self.angles[0]),
                timeout_s=self._rotation_move_timeout_s(current_angle, self.angles[0]),
            )
            self._capture_at_angle(float(self.angles[0]), result)
            self.progress.emit(100)
            return

        self._build_rotation_profiles()

        targets = self.angles
        direction = 1.0 if targets[-1] >= targets[0] else -1.0
        deltas = np.diff(targets)
        min_step = float(np.min(np.abs(deltas))) if deltas.size else 0.0
        tolerance = max(0.05, 0.45 * min_step) if min_step > 0 else 0.05

        self._apply_rotation_profile(self._rotation_fast_profile)
        current_angle = State.scanner.get_position(
            State.scanner.id_rotation,
            State.scanner.rotation_unit,
        )
        State.scanner.move_rotation(
            float(targets[0]),
            timeout_s=self._rotation_move_timeout_s(
                current_angle,
                targets[0],
                self._rotation_fast_profile.get("speed", self.fly_speed),
            ),
        )
        self.msleep(max(0, self.delay_ms))

        captured = 0
        missed = 0
        target_idx = 0
        if self._capture_at_angle(float(targets[target_idx]), result):
            captured += 1
            self.progress.emit(int(round(captured * 100 / targets.size)))
        target_idx += 1

        self._apply_rotation_profile(self._rotation_fly_profile)
        State.scanner.move_rotation_async(float(targets[-1]))

        travel = abs(float(targets[-1] - targets[0]))
        expected = travel / max(abs(self.fly_speed), 1e-6)
        timeout_s = max(2.0, expected * 4.0 + 2.0)
        started = time.time()

        while target_idx < targets.size and self._running:
            current_angle = float(
                State.scanner.get_position(
                    State.scanner.id_rotation,
                    State.scanner.rotation_unit,
                )
            )
            target_angle = float(targets[target_idx])
            delta = current_angle - target_angle

            if abs(delta) <= tolerance:
                if self._capture_at_angle(target_angle, result):
                    captured += 1
                    self.progress.emit(int(round(captured * 100 / targets.size)))
                target_idx += 1
                continue

            overshoot = (direction > 0 and delta > tolerance) or (
                direction < 0 and delta < -tolerance
            )
            if overshoot:
                if self._capture_at_angle(target_angle, result):
                    captured += 1
                    self.progress.emit(int(round(captured * 100 / targets.size)))
                else:
                    missed += 1
                target_idx += 1
                continue

            if time.time() - started > timeout_s:
                self.log.emit(
                    {
                        "type": "warning",
                        "msg": (
                            "Rotation fly timeout; "
                            f"captured={captured}, missed={missed}, total={targets.size}"
                        ),
                    }
                )
                break

            self.msleep(max(1, self.fly_poll_delay_ms))

        if not self._running:
            try:
                State.scanner.soft_stop(State.scanner.id_rotation)
            except Exception:
                pass

        try:
            State.scanner.wait_for_stop_rotation(timeout_s=5.0)
        except Exception as err:
            self.log.emit(
                {"type": "warning", "msg": f"Rotation stop wait failed: {err}"}
            )
        self._apply_rotation_profile(self._rotation_fast_profile)

        if missed > 0:
            self.log.emit(
                {
                    "type": "warning",
                    "msg": (
                        f"Rotation fly skipped {missed} targets. "
                        "Reduce fly speed or VNA measurement time."
                    ),
                }
            )

    def run(self):
        result = {
            "angle": [],
            "amplitude": [],
            "phase": [],
            "complex_real": [],
            "complex_imag": [],
            "vna_latency_ms": [],
        }
        try:
            self._configure_vna()
            if self.fly_mode:
                self._run_fly_mode(result)
            else:
                self._run_step_mode(result)

        except Exception as err:
            self.log.emit({"type": "error", "msg": f"Rotation measure error: {err}"})
        finally:
            self.finished_data.emit(result)


class RotationMeasureWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.measure_thread = None
        self.data = self._empty_data()

        layout = QVBoxLayout(self)
        controls_layout = QGridLayout()
        form_layout = QFormLayout()

        self.angle_start = DoubleSpinBox(self)
        self.angle_start.setRange(-36000, 36000)
        self.angle_start.setDecimals(3)
        self.angle_start.setValue(0)

        self.angle_stop = DoubleSpinBox(self)
        self.angle_stop.setRange(-36000, 36000)
        self.angle_stop.setDecimals(3)
        self.angle_stop.setValue(360)

        self.angle_points = QSpinBox(self)
        self.angle_points.setRange(1, 10000)
        self.angle_points.setValue(37)

        self.delay_ms = QSpinBox(self)
        self.delay_ms.setRange(0, 600000)
        self.delay_ms.setValue(200)

        self.fly_mode = QCheckBox("Fly mode", self)
        self.fly_mode.setChecked(False)
        self.fly_mode.setToolTip(
            "Move rotation axis continuously and sample VNA while moving"
        )
        self.fly_mode.toggled.connect(self.on_fly_mode_toggled)

        self.fly_speed = DoubleSpinBox(self)
        self.fly_speed.setRange(0.001, 100000)
        self.fly_speed.setDecimals(4)
        self.fly_speed.setValue(10)

        self.vna_points = QSpinBox(self)
        self.vna_points.setRange(1, 5000)
        self.vna_points.setValue(State.measure_vna_points)
        self.vna_parameter = QComboBox(self)
        for parameter in VNA_PARAMETER_OPTIONS:
            self.vna_parameter.addItem(parameter, parameter)
        current_parameter = normalize_vna_parameter(State.measure_vna_parameter)
        self.vna_parameter.setCurrentIndex(
            max(0, self.vna_parameter.findData(current_parameter))
        )
        self.vna_parameter.setToolTip("VNA measured quantity for rotation measurement")
        self.vna_parameter.currentIndexChanged.connect(self.on_vna_parameter_changed)

        self.vna_bandwidth = QSpinBox(self)
        self.vna_bandwidth.setRange(1, 1_000_000)
        self.vna_bandwidth.setSingleStep(100)
        self.vna_bandwidth.setValue(State.measure_vna_bandwidth)

        self.vna_power = DoubleSpinBox(self)
        self.vna_power.setRange(-100, 20)
        self.vna_power.setDecimals(1)
        self.vna_power.setValue(State.measure_vna_power)
        self.vna_power.setToolTip("VNA output power for rotation measurement, dBm")
        self.vna_power.valueChanged.connect(self.on_vna_power_changed)
        self.vna_output_enabled = QCheckBox(self)
        self.vna_output_enabled.setChecked(State.measure_vna_output_enabled)
        self.vna_output_enabled.setToolTip(
            "Enable VNA RF output during rotation measurement"
        )
        self.vna_output_enabled.toggled.connect(self.on_vna_output_enabled_changed)

        form_layout.addRow("Angle start, deg", self.angle_start)
        form_layout.addRow("Angle stop, deg", self.angle_stop)
        form_layout.addRow("Angle points", self.angle_points)
        form_layout.addRow("Delay, ms", self.delay_ms)
        form_layout.addRow(self.fly_mode)
        form_layout.addRow("Fly speed, deg/s", self.fly_speed)
        form_layout.addRow("VNA points", self.vna_points)
        form_layout.addRow("VNA parameter", self.vna_parameter)
        form_layout.addRow("VNA bandwidth, Hz", self.vna_bandwidth)
        form_layout.addRow("VNA power, dBm", self.vna_power)
        form_layout.addRow("VNA output enabled", self.vna_output_enabled)

        self.status_label = QLabel("Idle", self)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)

        self.btn_start = Button("Start Rotation Test", self, animate=True)
        self.btn_start.clicked.connect(self.start_measure)
        self.btn_stop = Button("Stop", self)
        self.btn_stop.clicked.connect(self.stop_measure)
        self.btn_stop.set_enabled(False)

        controls_layout.addLayout(form_layout, 0, 0, 1, 2)
        controls_layout.addWidget(self.status_label, 1, 0, 1, 2)
        controls_layout.addWidget(self.progress_bar, 2, 0, 1, 2)
        controls_layout.addWidget(self.btn_start, 3, 0)
        controls_layout.addWidget(self.btn_stop, 3, 1)

        self.amplitude_plot = pg.PlotWidget(title="Amplitude vs Angle")
        self.phase_plot = pg.PlotWidget(title="Phase vs Angle")
        for plot in (self.amplitude_plot, self.phase_plot):
            plot.setBackground("w")
            plot.showGrid(x=True, y=True, alpha=0.3)
            plot.setLabel("bottom", "Angle", units="deg")
            plot.setMinimumHeight(220)
        self.amplitude_plot.setLabel("left", "Amplitude", units="dB")
        self.phase_plot.setLabel("left", "Phase", units="rad")

        self.amplitude_curve = self.amplitude_plot.plot(
            [], [], pen=pg.mkPen((200, 40, 30), width=2), symbol="o", symbolSize=5
        )
        self.phase_curve = self.phase_plot.plot(
            [], [], pen=pg.mkPen((40, 80, 200), width=2), symbol="o", symbolSize=5
        )

        layout.addLayout(controls_layout)
        layout.addWidget(self.amplitude_plot)
        layout.addWidget(self.phase_plot)
        self.setLayout(layout)
        self.on_fly_mode_toggled(self.fly_mode.isChecked())

    @staticmethod
    def _empty_data():
        return {
            "angle": [],
            "amplitude": [],
            "phase": [],
            "complex_real": [],
            "complex_imag": [],
            "vna_latency_ms": [],
        }

    def _validate_ready(self):
        if not State.scanner:
            logger.warning("Scanner is not initialized!")
            return False
        if not State.scanner.id_rotation:
            logger.warning("Rotation axis is not initialized!")
            return False
        if not State.vna:
            logger.warning("VNA is not initialized!")
            return False
        return True

    def start_measure(self):
        if self.measure_thread and self.measure_thread.isRunning():
            logger.info("Rotation test is already running")
            return
        if not self._validate_ready():
            return
        if self.fly_mode.isChecked() and self.fly_speed.value() <= 0:
            logger.warning("Rotation fly speed must be > 0!")
            return

        self.data = self._empty_data()
        self._update_plots()
        angles = np.linspace(
            self.angle_start.value(),
            self.angle_stop.value(),
            self.angle_points.value(),
        )

        self.measure_thread = RotationMeasureThread(
            angles=angles,
            delay_ms=self.delay_ms.value(),
            vna_points=self.vna_points.value(),
            vna_bandwidth=self.vna_bandwidth.value(),
            vna_power=self.vna_power.value(),
            vna_parameter=str(self.vna_parameter.currentData()),
            vna_output_enabled=self.vna_output_enabled.isChecked(),
            fly_mode=self.fly_mode.isChecked(),
            fly_speed=self.fly_speed.value(),
            fly_poll_delay_ms=5,
        )
        self.measure_thread.point.connect(self.add_point)
        self.measure_thread.progress.connect(self.progress_bar.setValue)
        self.measure_thread.log.connect(self.set_log)
        self.measure_thread.finished.connect(self.on_finished)

        State.measure_vna_parameter = str(self.vna_parameter.currentData())
        State.measure_vna_power = self.vna_power.value()
        State.measure_vna_output_enabled = self.vna_output_enabled.isChecked()
        State.store_state()

        self.status_label.setText("Running")
        self.progress_bar.setValue(0)
        self.btn_start.set_enabled(False, animate=True)
        self.btn_stop.set_enabled(True)
        self.measure_thread.start()

    def on_fly_mode_toggled(self, enabled):
        self.fly_speed.setEnabled(enabled)
        self.delay_ms.setToolTip(
            "Settle pause after each angle in step mode; start pause before fly pass in fly mode."
        )

    @staticmethod
    def on_vna_power_changed(value):
        State.measure_vna_power = float(value)

    @staticmethod
    def on_vna_output_enabled_changed(value):
        State.measure_vna_output_enabled = bool(value)

    def on_vna_parameter_changed(self, _index):
        State.measure_vna_parameter = str(self.vna_parameter.currentData())

    def stop_measure(self):
        if self.measure_thread and self.measure_thread.isRunning():
            self.measure_thread.request_stop()
            if State.scanner:
                try:
                    State.scanner.soft_stop_all()
                except Exception as err:
                    logger.warning(f"Failed to stop scanner axes: {err}")
            self.status_label.setText("Stopping")

    def add_point(self, point):
        for key in self.data:
            self.data[key].append(point[key])
        self.status_label.setText(
            f"Angle {point['angle']:.3f} deg: "
            f"{point['amplitude']:.2f} dB, {point['phase']:.3f} rad"
        )
        self._update_plots()

    def _update_plots(self):
        angles = np.asarray(self.data["angle"], dtype=float)
        amplitude = np.asarray(self.data["amplitude"], dtype=float)
        phase = np.asarray(self.data["phase"], dtype=float)
        self.amplitude_curve.setData(angles, amplitude)
        self.phase_curve.setData(angles, phase)

    def on_finished(self):
        self.btn_start.set_enabled(True)
        self.btn_stop.set_enabled(False)
        if self.measure_thread and self.measure_thread._running:
            self.status_label.setText("Finished")
        elif self.status_label.text() == "Stopping":
            self.status_label.setText("Stopped")

    @staticmethod
    def set_log(log: dict):
        log_type = log.get("type")
        if not log_type:
            return
        method = getattr(logger, log_type, None)
        if not method:
            return
        method(log.get("msg"))
