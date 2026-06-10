import logging

import numpy as np
from PySide6.QtGui import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
    QCheckBox,
    QComboBox,
    QLineEdit,
)

from api.vna import VNA_PARAMETER_OPTIONS, normalize_vna_parameter
from application.measurement.config import (
    CenterCalibrationConfig,
    GeneratorSweepConfig,
    MeasurementConfig,
    MovementTimingConfig,
    SweepModeConfig,
    VnaConfig,
    build_axis_range,
    parse_amplitudes,
)
from application.measurement.planning import (
    AxisMotionProfile,
    MotionProfiles,
    build_measurement_plan,
    estimate_measurement_seconds,
)
from infrastructure.measurement.qt_measure_thread import MeasureThread
from interface.ui.Button import Button
from interface.ui.DoubleSpinBox import DoubleSpinBox
from interface.ui.Lines import HLine
from interface.ui.SpinBox import SpinBox
from store.state import State
from utils.functions import convert_seconds


logger = logging.getLogger(__name__)


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
        self.x_check.toggled.connect(self.update_approx_time)
        self.x_start = DoubleSpinBox(self)
        self.x_start.setRange(-1000, 1000)
        self.x_start.setValue(State.x_start)
        self.x_start.valueChanged.connect(self.update_x_step)
        self.x_start.valueChanged.connect(self.update_approx_time)
        self.x_stop = DoubleSpinBox(self)
        self.x_stop.setRange(-1000, 1000)
        self.x_stop.setValue(State.x_stop)
        self.x_stop.valueChanged.connect(self.update_x_step)
        self.x_stop.valueChanged.connect(self.update_approx_time)
        self.x_points = SpinBox(self)
        self.x_points.setRange(1, 5000)
        self.x_points.setValue(State.x_points)
        self.x_points.valueChanged.connect(self.update_x_step)
        self.x_points.valueChanged.connect(self.update_approx_time)
        self.x_step = DoubleSpinBox(self)
        self.x_step.setRange(0.02, 100)
        self.x_step.setSingleStep(0.0125)
        self.x_step.setValue(State.x_step)
        self.x_step.valueChanged.connect(self.update_x_points)

        self.y_check = QCheckBox("Y", self)
        self.y_check.setChecked(State.use_y_sweep)
        self.y_check.toggled.connect(self.update_approx_time)
        self.y_start = DoubleSpinBox(self)
        self.y_start.setRange(-1000, 1000)
        self.y_start.setValue(State.y_start)
        self.y_start.valueChanged.connect(self.update_y_step)
        self.y_start.valueChanged.connect(self.update_approx_time)
        self.y_stop = DoubleSpinBox(self)
        self.y_stop.setRange(-1000, 1000)
        self.y_stop.setValue(State.y_stop)
        self.y_stop.valueChanged.connect(self.update_y_step)
        self.y_stop.valueChanged.connect(self.update_approx_time)
        self.y_points = SpinBox(self)
        self.y_points.setRange(1, 5000)
        self.y_points.setValue(State.y_points)
        self.y_points.valueChanged.connect(self.update_y_step)
        self.y_points.valueChanged.connect(self.update_approx_time)
        self.y_step = DoubleSpinBox(self)
        self.y_step.setRange(0.02, 100)
        self.y_step.setSingleStep(0.0125)
        self.y_step.setValue(State.y_step)
        self.y_step.valueChanged.connect(self.update_y_points)

        self.z_check = QCheckBox("Z", self)
        self.z_check.setChecked(State.use_z_sweep)
        self.z_check.toggled.connect(self.update_approx_time)
        self.z_start = DoubleSpinBox(self)
        self.z_start.setRange(-1000, 1000)
        self.z_start.setValue(State.z_start)
        self.z_start.valueChanged.connect(self.update_z_step)
        self.z_start.valueChanged.connect(self.update_approx_time)
        self.z_stop = DoubleSpinBox(self)
        self.z_stop.setRange(-1000, 1000)
        self.z_stop.setValue(State.z_stop)
        self.z_stop.valueChanged.connect(self.update_z_step)
        self.z_stop.valueChanged.connect(self.update_approx_time)
        self.z_points = SpinBox(self)
        self.z_points.setRange(1, 5000)
        self.z_points.setValue(State.z_points)
        self.z_points.valueChanged.connect(self.update_z_step)
        self.z_points.valueChanged.connect(self.update_approx_time)
        self.z_step = DoubleSpinBox(self)
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
        self.rotation_start.valueChanged.connect(self.update_approx_time)
        self.rotation_stop = DoubleSpinBox(self)
        self.rotation_stop.setRange(-36000, 36000)
        self.rotation_stop.setDecimals(3)
        self.rotation_stop.setValue(State.rotation_stop)
        self.rotation_stop.valueChanged.connect(self.update_rotation_step)
        self.rotation_stop.valueChanged.connect(self.update_approx_time)
        self.rotation_points = SpinBox(self)
        self.rotation_points.setRange(1, 10000)
        self.rotation_points.setValue(State.rotation_points)
        self.rotation_points.valueChanged.connect(self.update_rotation_step)
        self.rotation_points.valueChanged.connect(self.update_approx_time)
        self.rotation_step = DoubleSpinBox(self)
        self.rotation_step.setRange(0.001, 36000)
        self.rotation_step.setDecimals(3)
        self.rotation_step.setValue(State.rotation_step)
        self.rotation_step.valueChanged.connect(self.update_rotation_points)

        self.z_snake_check = QCheckBox("Z Snake", self)
        self.z_snake_check.setChecked(State.use_z_snake_pattern)
        self.z_snake_check.setToolTip(
            "Enable snake pattern for Z-axis movement to reduce travel time"
        )
        self.z_snake_check.toggled.connect(self.update_approx_time)
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
        self.auto_adjust_z_fly_speed_check.toggled.connect(self.update_approx_time)
        self.z_fly_speed = DoubleSpinBox(self)
        self.z_fly_speed.setRange(0.01, 1000)
        self.z_fly_speed.setDecimals(4)
        self.z_fly_speed.setValue(State.z_fly_speed)
        self.z_fly_speed.valueChanged.connect(self.update_approx_time)

        self.vna_points = SpinBox(self)
        self.vna_points.setRange(1, 5000)
        self.vna_points.setValue(State.measure_vna_points)
        self.vna_points.valueChanged.connect(self.update_approx_time)
        self.vna_parameter = QComboBox(self)
        for parameter in VNA_PARAMETER_OPTIONS:
            self.vna_parameter.addItem(parameter, parameter)
        current_parameter = normalize_vna_parameter(State.measure_vna_parameter)
        self.vna_parameter.setCurrentIndex(
            max(0, self.vna_parameter.findData(current_parameter))
        )
        self.vna_parameter.setToolTip("VNA measured quantity for all scan points")
        self.vna_parameter.currentIndexChanged.connect(self.on_vna_parameter_changed)
        self.vna_power = DoubleSpinBox(self)
        self.vna_power.setRange(-100, 20)
        self.vna_power.setDecimals(1)
        self.vna_power.setValue(State.measure_vna_power)
        self.vna_power.setToolTip("VNA output power for all measurement points, dBm")
        self.vna_power.valueChanged.connect(self.on_vna_power_changed)
        self.vna_output_enabled = QCheckBox(self)
        self.vna_output_enabled.setChecked(State.measure_vna_output_enabled)
        self.vna_output_enabled.setToolTip("Enable VNA RF output during measurement")
        self.vna_output_enabled.toggled.connect(self.on_vna_output_enabled_changed)
        self.vna_cw_frequency_enabled = QCheckBox(self)
        self.vna_cw_frequency_enabled.setChecked(State.measure_vna_cw_frequency_enabled)
        self.vna_cw_frequency_enabled.setToolTip(
            "Sweep VNA CW frequency before each full scan block"
        )
        self.vna_cw_frequency_enabled.toggled.connect(
            self.on_vna_cw_frequency_enabled_changed
        )
        self.vna_cw_frequency_start = DoubleSpinBox(self)
        self.vna_cw_frequency_start.setRange(0.001, 1000)
        self.vna_cw_frequency_start.setDecimals(6)
        self.vna_cw_frequency_start.setValue(State.measure_vna_cw_frequency_start_ghz)
        self.vna_cw_frequency_stop = DoubleSpinBox(self)
        self.vna_cw_frequency_stop.setRange(0.001, 1000)
        self.vna_cw_frequency_stop.setDecimals(6)
        self.vna_cw_frequency_stop.setValue(State.measure_vna_cw_frequency_stop_ghz)
        self.vna_cw_frequency_points = SpinBox(self)
        self.vna_cw_frequency_points.setRange(1, 10000)
        self.vna_cw_frequency_points.setValue(State.measure_vna_cw_frequency_points)
        self.vna_cw_frequency_points.valueChanged.connect(self.update_approx_time)
        self.vna_start_time = DoubleSpinBox(self)
        self.vna_start_time.setRange(0, 1e6)
        self.vna_start_time.setDecimals(6)
        self.vna_start_time.setValue(State.measure_vna_start_time)
        self.vna_start_time.valueChanged.connect(self.update_approx_time)
        self.vna_stop_time = DoubleSpinBox(self)
        self.vna_stop_time.setRange(0, 1e6)
        self.vna_stop_time.setDecimals(6)
        self.vna_stop_time.setValue(State.measure_vna_stop_time)
        self.vna_stop_time.valueChanged.connect(self.update_approx_time)

        self.vna_bandwidth = SpinBox(self)
        self.vna_bandwidth.setRange(1, 1_000_000)
        self.vna_bandwidth.setSingleStep(100)
        self.vna_bandwidth.setValue(State.measure_vna_bandwidth)

        self.vna_average_enabled = QCheckBox(self)
        self.vna_average_enabled.setChecked(State.measure_vna_average_enabled)
        self.vna_average_count = SpinBox(self)
        self.vna_average_count.setRange(1, 1024)
        self.vna_average_count.setValue(State.measure_vna_average_count)
        self.vna_average_enabled.toggled.connect(self.vna_average_count.setEnabled)
        self.vna_average_enabled.toggled.connect(self.update_approx_time)
        self.vna_average_count.valueChanged.connect(self.update_approx_time)
        self.vna_average_count.setEnabled(self.vna_average_enabled.isChecked())

        self.plot_update_hz = DoubleSpinBox(self)
        self.plot_update_hz.setRange(0.01, 60.0)
        self.plot_update_hz.setDecimals(2)
        self.plot_update_hz.setSingleStep(0.25)
        self.plot_update_hz.setValue(State.plot_update_hz)
        self.plot_update_hz.setToolTip("How often live amplitude/phase images update")
        self.plot_update_hz.valueChanged.connect(self.on_plot_update_hz_changed)
        self.plot_max_pixels = SpinBox(self)
        self.plot_max_pixels.setRange(0, 20_000_000)
        self.plot_max_pixels.setSingleStep(100_000)
        self.plot_max_pixels.setSpecialValueText("Full resolution")
        self.plot_max_pixels.setValue(State.plot_max_pixels)
        self.plot_max_pixels.setToolTip(
            "0 renders every pixel. Higher values cap only the live frame resolution; full data is still stored."
        )
        self.plot_max_pixels.valueChanged.connect(self.on_plot_max_pixels_changed)

        self.center_calibration_enabled = QCheckBox(self)
        self.center_calibration_enabled.setChecked(State.center_calibration_enabled)
        self.center_calibration_enabled.setToolTip(
            "Return to the center point after a configured number of completed Z lines"
        )
        self.center_calibration_enabled.toggled.connect(self.update_approx_time)
        self.center_calibration_enabled.toggled.connect(
            self._set_center_calibration_controls_enabled
        )
        self.center_calibration_x = DoubleSpinBox(self)
        self.center_calibration_x.setRange(-1000, 1000)
        self.center_calibration_x.setDecimals(4)
        self.center_calibration_x.setValue(State.center_calibration_x)
        self.center_calibration_y = DoubleSpinBox(self)
        self.center_calibration_y.setRange(-1000, 1000)
        self.center_calibration_y.setDecimals(4)
        self.center_calibration_y.setValue(State.center_calibration_y)
        self.center_calibration_z = DoubleSpinBox(self)
        self.center_calibration_z.setRange(-1000, 1000)
        self.center_calibration_z.setDecimals(4)
        self.center_calibration_z.setValue(State.center_calibration_z)
        self.center_calibration_period_lines = SpinBox(self)
        self.center_calibration_period_lines.setRange(1, 1_000_000)
        self.center_calibration_period_lines.setValue(
            max(1, State.center_calibration_period_lines)
        )
        self.center_calibration_period_lines.setToolTip(
            "Calibration period measured in fully completed Z scan lines"
        )
        self.center_calibration_period_lines.valueChanged.connect(
            self.update_approx_time
        )

        self.generator_freq_start_1 = DoubleSpinBox(self)
        self.generator_freq_start_1.setRange(1, 1000)
        self.generator_freq_start_1.setDecimals(5)
        self.generator_freq_start_1.setValue(State.generator_freq_start_1)

        self.generator_freq_stop_1 = DoubleSpinBox(self)
        self.generator_freq_stop_1.setRange(1, 1000)
        self.generator_freq_stop_1.setDecimals(5)
        self.generator_freq_stop_1.setValue(State.generator_freq_stop_1)

        self.generator_freq_points_1 = SpinBox(self)
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

        self.generator_freq_points_2 = SpinBox(self)
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
        f_layout.addRow("VNA parameter", self.vna_parameter)
        f_layout.addRow("VNA power, dBm", self.vna_power)
        f_layout.addRow("VNA output enabled", self.vna_output_enabled)
        f_layout.addRow("VNA CW sweep", self.vna_cw_frequency_enabled)
        f_layout.addRow("VNA CW start, GHz", self.vna_cw_frequency_start)
        f_layout.addRow("VNA CW stop, GHz", self.vna_cw_frequency_stop)
        f_layout.addRow("VNA CW points", self.vna_cw_frequency_points)
        f_layout.addRow("VNA start time, s", self.vna_start_time)
        f_layout.addRow("VNA stop time, s", self.vna_stop_time)
        f_layout.addRow("VNA bandwidth, Hz", self.vna_bandwidth)
        f_layout.addRow("VNA average", self.vna_average_enabled)
        f_layout.addRow("VNA average count", self.vna_average_count)
        f_layout.addRow("Plot update, Hz", self.plot_update_hz)
        f_layout.addRow("Plot max pixels", self.plot_max_pixels)
        f_layout.addRow("Center calibration", self.center_calibration_enabled)
        f_layout.addRow("Calibration X, mm", self.center_calibration_x)
        f_layout.addRow("Calibration Y, mm", self.center_calibration_y)
        f_layout.addRow("Calibration Z, mm", self.center_calibration_z)
        f_layout.addRow(
            "Calibration period, Z lines",
            self.center_calibration_period_lines,
        )

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
        self._set_center_calibration_controls_enabled(
            self.center_calibration_enabled.isChecked()
        )
        self._set_vna_cw_frequency_controls_enabled(
            self.vna_cw_frequency_enabled.isChecked()
        )
        self.update_approx_time()

    def on_z_fly_toggled(self, enabled):
        self.z_fly_speed.setEnabled(enabled)
        self.auto_adjust_z_fly_speed_check.setEnabled(enabled)
        if enabled:
            self.z_snake_check.setChecked(False)
            self.z_snake_check.setEnabled(False)
        else:
            self.z_snake_check.setEnabled(True)
        self.update_approx_time()

    def _set_center_calibration_controls_enabled(self, enabled):
        for widget in (
            self.center_calibration_x,
            self.center_calibration_y,
            self.center_calibration_z,
            self.center_calibration_period_lines,
        ):
            widget.setEnabled(enabled)

    @staticmethod
    def on_plot_update_hz_changed(value):
        State.plot_update_hz = float(value)

    @staticmethod
    def on_plot_max_pixels_changed(value):
        State.plot_max_pixels = int(value)

    @staticmethod
    def on_vna_power_changed(value):
        State.measure_vna_power = float(value)

    @staticmethod
    def on_vna_output_enabled_changed(value):
        State.measure_vna_output_enabled = bool(value)

    def on_vna_cw_frequency_enabled_changed(self, value):
        State.measure_vna_cw_frequency_enabled = bool(value)
        self._set_vna_cw_frequency_controls_enabled(bool(value))
        self.update_approx_time()

    def _set_vna_cw_frequency_controls_enabled(self, enabled):
        for widget in (
            self.vna_cw_frequency_start,
            self.vna_cw_frequency_stop,
            self.vna_cw_frequency_points,
        ):
            widget.setEnabled(enabled)

    def on_vna_parameter_changed(self, _index):
        State.measure_vna_parameter = str(self.vna_parameter.currentData())

    def _build_measurement_config(self) -> MeasurementConfig:
        return MeasurementConfig(
            x_range=build_axis_range(
                start=self.x_start.value(),
                stop=self.x_stop.value(),
                points=self.x_points.value(),
                enabled=self.x_check.isChecked(),
            ),
            y_range=build_axis_range(
                start=self.y_start.value(),
                stop=self.y_stop.value(),
                points=self.y_points.value(),
                enabled=self.y_check.isChecked(),
            ),
            z_range=build_axis_range(
                start=self.z_start.value(),
                stop=self.z_stop.value(),
                points=self.z_points.value(),
                enabled=self.z_check.isChecked(),
            ),
            rotation_range=build_axis_range(
                start=self.rotation_start.value(),
                stop=self.rotation_stop.value(),
                points=self.rotation_points.value(),
                enabled=self.rotation_check.isChecked(),
            ),
            vna=VnaConfig(
                power=self.vna_power.value(),
                start_time=self.vna_start_time.value(),
                stop_time=self.vna_stop_time.value(),
                points=self.vna_points.value(),
                bandwidth=self.vna_bandwidth.value(),
                average_count=self.vna_average_count.value(),
                average_enabled=self.vna_average_enabled.isChecked(),
                parameter=str(self.vna_parameter.currentData()),
                output_enabled=self.vna_output_enabled.isChecked(),
                cw_frequency_enabled=self.vna_cw_frequency_enabled.isChecked(),
                cw_frequency_start_ghz=self.vna_cw_frequency_start.value(),
                cw_frequency_stop_ghz=self.vna_cw_frequency_stop.value(),
                cw_frequency_points=self.vna_cw_frequency_points.value(),
            ),
            generator_1=GeneratorSweepConfig(
                freq_start=self.generator_freq_start_1.value(),
                freq_stop=self.generator_freq_stop_1.value(),
                freq_points=self.generator_freq_points_1.value(),
                amplitudes=parse_amplitudes(self.generator_amps_1.text()),
            ),
            generator_2=GeneratorSweepConfig(
                freq_start=self.generator_freq_start_2.value(),
                freq_stop=self.generator_freq_stop_2.value(),
                freq_points=self.generator_freq_points_2.value(),
                amplitudes=parse_amplitudes(self.generator_amps_2.text()),
            ),
            sweep=SweepModeConfig(
                use_x=self.x_check.isChecked(),
                use_y=self.y_check.isChecked(),
                use_z=self.z_check.isChecked(),
                use_z_snake_pattern=self.z_snake_check.isChecked(),
                use_z_fly_mode=self.z_fly_check.isChecked(),
                z_fly_speed=self.z_fly_speed.value(),
                auto_adjust_z_fly_speed=self.auto_adjust_z_fly_speed_check.isChecked(),
                use_rotation=self.rotation_check.isChecked(),
            ),
            movement=MovementTimingConfig(
                x_delay_ms=State.x_movement_delay,
                y_delay_ms=State.y_movement_delay,
                z_delay_ms=State.z_movement_delay,
                no_movement_delay_ms=State.no_movement_delay,
                fly_poll_delay_ms=max(
                    1,
                    int(min(50, State.no_movement_delay // 5 or 1)),
                ),
            ),
            center_calibration=CenterCalibrationConfig(
                enabled=self.center_calibration_enabled.isChecked(),
                x=self.center_calibration_x.value(),
                y=self.center_calibration_y.value(),
                z=self.center_calibration_z.value(),
                period_lines=self.center_calibration_period_lines.value(),
            ),
            plot_update_hz=self.plot_update_hz.value(),
        )

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
        if self.center_calibration_enabled.isChecked():
            missing_calibration_axes = []
            if self.x_check.isChecked() and not State.scanner.id_x:
                missing_calibration_axes.append("X")
            if self.y_check.isChecked() and not State.scanner.id_y:
                missing_calibration_axes.append("Y")
            if self.z_check.isChecked() and not State.scanner.id_z:
                missing_calibration_axes.append("Z")
            if missing_calibration_axes:
                logger.warning(
                    "Center calibration requires initialized enabled axes: "
                    + ", ".join(missing_calibration_axes)
                )
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
        State.measure_vna_parameter = str(self.vna_parameter.currentData())
        State.measure_vna_power = self.vna_power.value()
        State.measure_vna_output_enabled = self.vna_output_enabled.isChecked()
        State.measure_vna_cw_frequency_enabled = (
            self.vna_cw_frequency_enabled.isChecked()
        )
        State.measure_vna_cw_frequency_start_ghz = self.vna_cw_frequency_start.value()
        State.measure_vna_cw_frequency_stop_ghz = self.vna_cw_frequency_stop.value()
        State.measure_vna_cw_frequency_points = self.vna_cw_frequency_points.value()
        State.measure_vna_start_time = self.vna_start_time.value()
        State.measure_vna_stop_time = self.vna_stop_time.value()
        State.measure_vna_bandwidth = self.vna_bandwidth.value()
        State.measure_vna_average_enabled = self.vna_average_enabled.isChecked()
        State.measure_vna_average_count = self.vna_average_count.value()
        State.plot_update_hz = self.plot_update_hz.value()
        State.plot_max_pixels = self.plot_max_pixels.value()
        State.center_calibration_enabled = self.center_calibration_enabled.isChecked()
        State.center_calibration_x = self.center_calibration_x.value()
        State.center_calibration_y = self.center_calibration_y.value()
        State.center_calibration_z = self.center_calibration_z.value()
        State.center_calibration_period_lines = (
            self.center_calibration_period_lines.value()
        )

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

        self.measure_thread = MeasureThread.from_config(
            self._build_measurement_config()
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
        config = self._build_measurement_config()
        plan = build_measurement_plan(config)
        seconds = estimate_measurement_seconds(config, self._motion_profiles())
        self.approx_time.setText(
            f"Approx time ~ {convert_seconds(int(round(seconds)))} ({plan.total_steps} points)"
        )

    @staticmethod
    def _motion_profiles() -> MotionProfiles:
        return MotionProfiles(
            x=AxisMotionProfile(
                State.scanner_x_speed,
                State.scanner_x_accel,
                State.scanner_x_decel,
            ),
            y=AxisMotionProfile(
                State.scanner_y_speed,
                State.scanner_y_accel,
                State.scanner_y_decel,
            ),
            z=AxisMotionProfile(
                State.scanner_z_speed,
                State.scanner_z_accel,
                State.scanner_z_decel,
            ),
            rotation=AxisMotionProfile(
                State.scanner_rotation_speed,
                State.scanner_rotation_accel,
                State.scanner_rotation_decel,
            ),
        )

    @staticmethod
    def set_log(log: dict):
        log_type = log.get("type")
        if not log_type:
            return
        method = getattr(logger, log_type, None)
        if not method:
            return
        method(log.get("msg"))
