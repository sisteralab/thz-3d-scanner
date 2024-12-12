import json
import time
from datetime import datetime

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
)

from interface.ui.Button import Button
from interface.ui.DoubleSpinBox import DoubleSpinBox
from store.state import State
from utils.functions import steps_to_time, convert_seconds


class MeasureThread(QThread):
    data = Signal(dict)
    progress = Signal(int)
    remaining_time = Signal(str)

    def __init__(
        self, x_range, y_range, z_range, vna_power, vna_start, vna_stop, vna_points
    ):
        super().__init__()
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
        self.vna_power = vna_power
        self.vna_start = vna_start
        self.vna_stop = vna_stop
        self.vna_points = vna_points

    def run(self):
        State.vna.set_parameter("BA")
        State.vna.set_start_time(self.vna_start)
        State.vna.set_stop_time(self.vna_stop)
        State.vna.set_sweep(self.vna_points)
        State.vna.set_power(self.vna_power)
        State.vna.set_channel_format("COMP")
        State.vna.set_average_count(10)
        State.vna.set_average_status(False)
        full_data = {
            "x": self.x_range.tolist(),
            "y": self.y_range.tolist(),
            "z": self.z_range.tolist(),
            "amplitude": np.zeros((len(self.x_range), len(self.z_range))).tolist(),
            "vna_data": [],
        }
        total_steps = len(self.y_range) * len(self.x_range) * len(self.z_range)
        step = 0
        start_time = time.time()
        for step_y, y in enumerate(self.y_range):
            State.d3.move_y(y)
            if not State.measure_running:
                break
            for step_x, x in enumerate(self.x_range):
                State.d3.move_x(x)
                if not State.measure_running:
                    break
                for step_z, z in enumerate(self.z_range):
                    State.d3.move_z(z)
                    self.msleep(50)
                    vna_data = State.vna.get_data()
                    dat = np.mean(vna_data["amplitude"])
                    print(f"{datetime.now()} {dat} dB")
                    full_data["amplitude"][step_x][step_z] = dat
                    full_data["vna_data"].append(vna_data)
                    self.data.emit(full_data)
                    step += 1
                    now_time = time.time()
                    velocity = step / (now_time - start_time)
                    self.progress.emit(int(round(step * 100 / total_steps)))
                    self.remaining_time.emit(
                        f"Approx time ~ {convert_seconds(round((total_steps - step) / velocity))}"
                    )
                    if not State.measure_running:
                        break

        with open(
            f"data/meas_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json",
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(full_data, f, ensure_ascii=False, indent=4)


class MeasureWidget(QGroupBox):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle("Measure")

        self.measure_thread = None

        layout = QVBoxLayout()
        g_layout = QGridLayout()
        f_layout = QFormLayout()
        h_layout = QHBoxLayout()

        self.x_start = DoubleSpinBox(self)
        self.x_start.setRange(-1000, 1000)
        self.x_start.setValue(-10)
        self.x_start.valueChanged.connect(self.update_x_step)
        self.x_stop = DoubleSpinBox(self)
        self.x_stop.setRange(-1000, 1000)
        self.x_stop.setValue(-90)
        self.x_stop.valueChanged.connect(self.update_x_step)
        self.x_points = QSpinBox(self)
        self.x_points.setRange(1, 5000)
        self.x_points.setValue(4)
        self.x_points.valueChanged.connect(self.update_x_step)
        self.x_points.valueChanged.connect(self.update_approx_time)
        self.x_step = QDoubleSpinBox(self)
        self.x_step.setRange(0.02, 100)
        self.x_step.setSingleStep(0.0125)
        self.x_step.valueChanged.connect(self.update_x_points)

        self.y_start = DoubleSpinBox(self)
        self.y_start.setRange(-1000, 1000)
        self.y_start.setValue(-60)
        self.y_start.valueChanged.connect(self.update_y_step)
        self.y_stop = DoubleSpinBox(self)
        self.y_stop.setRange(-1000, 1000)
        self.y_stop.setValue(-60)
        self.y_stop.valueChanged.connect(self.update_y_step)
        self.y_points = QSpinBox(self)
        self.y_points.setRange(1, 5000)
        self.y_points.valueChanged.connect(self.update_y_step)
        self.y_points.valueChanged.connect(self.update_approx_time)
        self.y_step = QDoubleSpinBox(self)
        self.y_step.setRange(0.02, 100)
        self.y_step.setSingleStep(0.0125)
        self.y_step.valueChanged.connect(self.update_y_points)

        self.z_start = DoubleSpinBox(self)
        self.z_start.setRange(-1000, 1000)
        self.z_start.setValue(70)
        self.z_start.valueChanged.connect(self.update_z_step)
        self.z_stop = DoubleSpinBox(self)
        self.z_stop.setRange(-1000, 1000)
        self.z_stop.setValue(90)
        self.z_stop.valueChanged.connect(self.update_z_step)
        self.z_points = QSpinBox(self)
        self.z_points.setRange(1, 5000)
        self.z_points.setValue(4)
        self.z_points.valueChanged.connect(self.update_z_step)
        self.z_points.valueChanged.connect(self.update_approx_time)
        self.z_step = QDoubleSpinBox(self)
        self.z_step.setRange(0.02, 100)
        self.z_step.setSingleStep(0.0125)
        self.z_step.valueChanged.connect(self.update_z_points)

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

        self.approx_time = QLabel("Approx time ~ None", self)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)

        self.btn_start_measure = Button("Start", self, animate=True)
        self.btn_start_measure.clicked.connect(self.start_measure)

        self.btn_stop_measure = Button("Stop", self)
        self.btn_stop_measure.clicked.connect(self.stop_measure)
        self.btn_stop_measure.set_enabled(False)

        g_layout.addWidget(QLabel("Axis", self), 0, 0, alignment=Qt.AlignCenter)
        g_layout.addWidget(QLabel("Start", self), 0, 1, alignment=Qt.AlignCenter)
        g_layout.addWidget(QLabel("Stop", self), 0, 2, alignment=Qt.AlignCenter)
        g_layout.addWidget(QLabel("Points", self), 0, 3, alignment=Qt.AlignCenter)
        g_layout.addWidget(QLabel("Step", self), 0, 4, alignment=Qt.AlignCenter)

        g_layout.addWidget(QLabel("X", self), 1, 0, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.x_start, 1, 1, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.x_stop, 1, 2, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.x_points, 1, 3, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.x_step, 1, 4, alignment=Qt.AlignCenter)

        g_layout.addWidget(QLabel("Y", self), 2, 0, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.y_start, 2, 1, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.y_stop, 2, 2, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.y_points, 2, 3, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.y_step, 2, 4, alignment=Qt.AlignCenter)

        g_layout.addWidget(QLabel("Z", self), 3, 0, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.z_start, 3, 1, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.z_stop, 3, 2, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.z_points, 3, 3, alignment=Qt.AlignCenter)
        g_layout.addWidget(self.z_step, 3, 4, alignment=Qt.AlignCenter)

        # f_layout.addRow("VNA power, dBm", self.vna_power)
        # f_layout.addRow("VNA start time, s", self.vna_start_time)
        # f_layout.addRow("VNA stop time, s", self.vna_stop_time)
        # f_layout.addRow("VNA points", self.vna_points)

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
        self.measure_thread = MeasureThread(
            x_range=np.linspace(
                self.x_start.value(), self.x_stop.value(), self.x_points.value()
            ),
            y_range=np.linspace(
                self.y_start.value(), self.y_stop.value(), self.y_points.value()
            ),
            z_range=np.linspace(
                self.z_start.value(), self.z_stop.value(), self.z_points.value()
            ),
            vna_power=-90,
            vna_start=0,
            vna_stop=0.1,
            vna_points=100,
        )

        self.measure_thread.data.connect(self.parent().parent().parent().update_plot)
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
        steps = self.x_points.value() * self.y_points.value() * self.z_points.value()
        self.approx_time.setText(f"Approx time ~ {steps_to_time(steps)}")
