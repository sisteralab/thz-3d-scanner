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
        use_x_sweep=True,
        use_y_sweep=True,
        use_z_sweep=True,
        use_z_snake_pattern=True,
        x_movement_delay=100,
        y_movement_delay=150,
        z_movement_delay=200,
        no_movement_delay=50,
    ):
        super().__init__()
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
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
        self.use_x_sweep = use_x_sweep
        self.use_y_sweep = use_y_sweep
        self.use_z_sweep = use_z_sweep
        self.use_z_snake_pattern = use_z_snake_pattern
        self.x_movement_delay = x_movement_delay
        self.y_movement_delay = y_movement_delay
        self.z_movement_delay = z_movement_delay
        self.no_movement_delay = no_movement_delay

        self.measure = MeasureModel.objects.create(data=[])
        self.measure.save(False)

    def run(self):
        try:
            State.vna.set_parameter("BA")
            State.vna.set_start_time(self.vna_start)
            State.vna.set_stop_time(self.vna_stop)
            State.vna.set_sweep(self.vna_points)
            State.vna.set_power(self.vna_power)
            State.vna.set_channel_format("COMP")
            State.vna.set_average_count(10)
            State.vna.set_average_status(False)
            State.vna.set_bandwidth(1000)

            freq_points = np.min(
                [self.generator_freq_points_1, self.generator_freq_points_2]
            )
            if type(self.generator_amps_1) == list:
                if len(self.generator_amps_1) >= freq_points:
                    self.generator_amps_1 = self.generator_amps_1[:freq_points]
                elif len(self.generator_amps_1) >= 1:
                    diff = freq_points - len(self.generator_amps_1)
                    self.generator_amps_1.extend(
                        [self.generator_amps_1[-1] for _ in range(diff)]
                    )
                else:
                    self.generator_amps_1 = [None for _ in range(freq_points)]

            total_steps = (
                len(self.y_range) * len(self.x_range) * len(self.z_range) * freq_points
            )
            step = 0
            start_time = time.time()

            freq_range_1 = np.linspace(
                self.generator_freq_start_1, self.generator_freq_stop_1, freq_points
            )
            freq_range_2 = np.linspace(
                self.generator_freq_start_2, self.generator_freq_stop_2, freq_points
            )
            stop_requested = False
            for freq_1, amp_1, freq_2 in zip(
                freq_range_1, self.generator_amps_1, freq_range_2
            ):
                print(f"AMP 1: {amp_1}")
                if amp_1 is not None:
                    State.generator_1.set_power(-100)
                State.generator_1.set_frequency(freq_1 * 1e9)
                if amp_1 is not None:
                    State.generator_1.set_power(amp_1)
                State.generator_2.set_frequency(freq_2 * 1e9)

                full_data = {
                    "freq_1": freq_1,
                    "amp_1": amp_1,
                    "freq_2": freq_2,
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
                }
                preview_data = {
                    "freq_1": freq_1,
                    "amp_1": amp_1,
                    "freq_2": freq_2,
                    "x": full_data["x"],
                    "y": full_data["y"],
                    "z": full_data["z"],
                    "amplitude": full_data["amplitude"],
                    "phase": full_data["phase"],
                    "complex_real": full_data["complex_real"],
                    "complex_imag": full_data["complex_imag"],
                }
                freq_has_data = False

                for step_y, y in enumerate(self.y_range):
                    if self.use_y_sweep:
                        State.scanner.move_y(y)
                        self.msleep(self.y_movement_delay)
                    if not State.measure_running:
                        stop_requested = True
                        break
                    for step_x, x in enumerate(self.x_range):
                        if self.use_x_sweep:
                            State.scanner.move_x(x)
                            self.msleep(self.x_movement_delay)
                        if not State.measure_running:
                            stop_requested = True
                            break

                        # Z-axis snake pattern with optimized movement
                        if self.use_z_snake_pattern:
                            # Create efficient snake pattern for Z-axis
                            # Alternate direction for each X row to minimize travel distance
                            # while ensuring full coverage of the Z range
                            if step_x % 2 == 0:
                                z_indices = range(len(self.z_range))
                            else:
                                z_indices = reversed(range(len(self.z_range)))
                        else:
                            # Standard linear traversal from start to end
                            z_indices = range(len(self.z_range))

                        for z_idx in z_indices:
                            z = self.z_range[z_idx]
                            if self.use_z_sweep:
                                State.scanner.move_z(z)
                                self.msleep(self.z_movement_delay)
                            else:
                                self.msleep(self.no_movement_delay)
                            m_s_time = time.time()
                            vna_data = State.vna.get_data()
                            print(f"Meas time {time.time() - m_s_time} s")
                            real = np.asarray(vna_data.get("real", []), dtype=np.float32)
                            imag = np.asarray(vna_data.get("imag", []), dtype=np.float32)
                            points_count = int(min(real.size, imag.size))
                            if points_count == 0:
                                continue
                            mean_real = float(np.mean(real[:points_count], dtype=np.float64))
                            mean_imag = float(np.mean(imag[:points_count], dtype=np.float64))
                            dat = float(
                                20 * np.log10(max(np.hypot(mean_real, mean_imag), 1e-12))
                            )
                            phase = float(np.arctan2(mean_imag, mean_real))
                            self.log.emit(
                                {
                                    "type": "info",
                                    "msg": f"freq1 {freq_1:.5f}GHz; freq2 {freq_2:.5f}GHz; pow {dat:.5f} dB; phase {phase:.2f}",
                                }
                            )
                            # Store full 3D tensor as [y_idx][x_idx][z_idx].
                            full_data["amplitude"][step_y][step_x][z_idx] = dat
                            full_data["phase"][step_y][step_x][z_idx] = phase
                            full_data["complex_real"][step_y][step_x][z_idx] = mean_real
                            full_data["complex_imag"][step_y][step_x][z_idx] = mean_imag
                            freq_has_data = True
                            # Emit only lightweight data needed by live plots.
                            self.data.emit(preview_data)
                            step += 1
                            now_time = time.time()
                            velocity = step / (now_time - start_time)
                            self.progress.emit(int(round(step * 100 / total_steps)))
                            self.remaining_time.emit(
                                f"Approx time ~ {convert_seconds(round((total_steps - step) / velocity))}"
                            )
                            if not State.measure_running:
                                stop_requested = True
                                break
                        if stop_requested:
                            break
                    if stop_requested:
                        break

                if freq_has_data:
                    self.measure.data.append(full_data)
                if stop_requested:
                    break

        except (AttributeError, Exception) as e:
            self.log.emit({"type": "error", "msg": f"{e}"})

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

        self.z_snake_check = QCheckBox("Z Snake", self)
        self.z_snake_check.setChecked(State.use_z_snake_pattern)
        self.z_snake_check.setToolTip(
            "Enable snake pattern for Z-axis movement to reduce travel time"
        )

        # self.vna_power = DoubleSpinBox(self)
        # self.vna_power.setRange(-90, 8)
        # self.vna_power.setValue(-90)
        # self.vna_start_time = DoubleSpinBox(self)
        # self.vna_start_time.setRange(0.001, 10)
        # self.vna_stop_time = DoubleSpinBox(self)
        # self.vna_stop_time.setRange(0.001, 10)
        # self.vna_points = QSpinBox(self)
        # self.vna_points.setRange(1, 5000)
        # self.vna_points.setValue(100)

        self.generator_freq_start_1 = DoubleSpinBox(self)
        self.generator_freq_start_1.setRange(1, 290)
        self.generator_freq_start_1.setDecimals(5)
        self.generator_freq_start_1.setValue(State.generator_freq_start_1)

        self.generator_freq_stop_1 = DoubleSpinBox(self)
        self.generator_freq_stop_1.setRange(1, 290)
        self.generator_freq_stop_1.setDecimals(5)
        self.generator_freq_stop_1.setValue(State.generator_freq_stop_1)

        self.generator_freq_points_1 = QSpinBox(self)
        self.generator_freq_points_1.setRange(1, 290)
        self.generator_freq_points_1.setValue(State.generator_freq_points_1)
        self.generator_freq_points_1.valueChanged.connect(self.update_approx_time)

        self.generator_amps_1 = QLineEdit(self)
        self.generator_amps_1.setText(State.generator_amps_1)

        self.generator_freq_start_2 = DoubleSpinBox(self)
        self.generator_freq_start_2.setRange(1, 290)
        self.generator_freq_start_2.setDecimals(5)
        self.generator_freq_start_2.setValue(State.generator_freq_start_2)

        self.generator_freq_stop_2 = DoubleSpinBox(self)
        self.generator_freq_stop_2.setRange(1, 290)
        self.generator_freq_stop_2.setDecimals(5)
        self.generator_freq_stop_2.setValue(State.generator_freq_stop_2)

        self.generator_freq_points_2 = QSpinBox(self)
        self.generator_freq_points_2.setRange(1, 290)
        self.generator_freq_points_2.setValue(State.generator_freq_points_2)
        self.generator_freq_points_2.valueChanged.connect(self.update_approx_time)

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
            self.z_snake_check, 4, 0, alignment=Qt.AlignmentFlag.AlignLeft
        )

        # f_layout.addRow("VNA power, dBm", self.vna_power)
        # f_layout.addRow("VNA start time, s", self.vna_start_time)
        # f_layout.addRow("VNA stop time, s", self.vna_stop_time)
        # f_layout.addRow("VNA points", self.vna_points)

        f_layout.addRow(HLine(self))

        f_layout.addRow("Generator start 1, GHz", self.generator_freq_start_1)
        f_layout.addRow("Generator stop 1, GHz", self.generator_freq_stop_1)
        f_layout.addRow("Generator points 1", self.generator_freq_points_1)
        f_layout.addRow("Generator amps 1", self.generator_amps_1)

        f_layout.addRow(HLine(self))

        f_layout.addRow("Generator start 2, GHz", self.generator_freq_start_2)
        f_layout.addRow("Generator stop 2, GHz", self.generator_freq_stop_2)
        f_layout.addRow("Generator points 2", self.generator_freq_points_2)

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
        self.update_approx_time()

    def start_measure(self):
        if self.generator_freq_points_2.value() != self.generator_freq_points_1.value():
            logger.warning("Frequency points must be equal!")
            return

        State.generator_freq_start_1 = self.generator_freq_start_1.value()
        State.generator_freq_stop_1 = self.generator_freq_stop_1.value()
        State.generator_freq_points_1 = self.generator_freq_points_1.value()
        State.generator_amps_1 = self.generator_amps_1.text()
        State.generator_freq_start_2 = self.generator_freq_start_2.value()
        State.generator_freq_stop_2 = self.generator_freq_stop_2.value()
        State.generator_freq_points_2 = self.generator_freq_points_2.value()

        State.use_x_sweep = self.x_check.isChecked()
        State.use_y_sweep = self.y_check.isChecked()
        State.use_z_sweep = self.z_check.isChecked()
        State.use_z_snake_pattern = self.z_snake_check.isChecked()

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

        amps_1 = []
        raw_amps_1 = self.generator_amps_1.text().replace(" ", "").split(",")
        for a in raw_amps_1:
            try:
                a = float(a)
                amps_1.append(a)
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
            vna_power=-30,
            vna_start=0,
            vna_stop=0.1,
            vna_points=100,
            generator_freq_start_1=self.generator_freq_start_1.value(),
            generator_freq_stop_1=self.generator_freq_stop_1.value(),
            generator_freq_points_1=self.generator_freq_points_1.value(),
            generator_amps_1=amps_1,
            generator_freq_start_2=self.generator_freq_start_2.value(),
            generator_freq_stop_2=self.generator_freq_stop_2.value(),
            generator_freq_points_2=self.generator_freq_points_2.value(),
            use_x_sweep=self.x_check.isChecked(),
            use_y_sweep=self.y_check.isChecked(),
            use_z_sweep=self.z_check.isChecked(),
            use_z_snake_pattern=self.z_snake_check.isChecked(),
            x_movement_delay=State.x_movement_delay,
            y_movement_delay=State.y_movement_delay,
            z_movement_delay=State.z_movement_delay,
            no_movement_delay=State.no_movement_delay,
        )

        self.measure_thread.data.connect(
            self.parent()
            .parent()
            .parent()
            .parent()
            .parent()
            .parent()
            .parent()
            .parent()
            .update_plot
        )  # FIXME: fix parents later
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

    def update_approx_time(self):
        steps = (
            self.x_points.value()
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
