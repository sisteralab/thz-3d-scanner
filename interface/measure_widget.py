import json
from datetime import datetime

import numpy as np

from PySide6.QtWidgets import (
    QHBoxLayout,
    QVBoxLayout,
    QFormLayout,
    QSpinBox,
    QPushButton,
    QGroupBox,
)
from PySide6.QtCore import QThread, Signal

from interface.ui.DoubleSpinBox import DoubleSpinBox
from interface.ui.Lines import HLine
from store.state import State


class MeasureThread(QThread):
    data = Signal(dict)
    progress = Signal(int)

    def __init__(
            self,
            x_range,
            y_range,
            z_range,
            vna_power,
            vna_start,
            vna_stop,
            vna_points
    ):
        super().__init__()
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
        self.vna_power = vna_power
        self.vna_start = vna_start
        self.vna_stop = vna_stop
        self.vna_points = vna_points

        self.init_x = State.d3.get_position(State.d3.id_x)
        self.init_y = State.d3.get_position(State.d3.id_y)
        self.init_z = State.d3.get_position(State.d3.id_z)

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
        for step_y, y in enumerate(self.y_range):
            State.d3.move_y(y)
            self.msleep(500)
            if not State.measure_running:
                break
            for step_x, x in enumerate(self.x_range):
                State.d3.move_x(x)
                if not State.measure_running:
                    break
                for step_z, z in enumerate(self.z_range):
                    State.d3.move_z(z)
                    self.msleep(3000)
                    vna_data = State.vna.get_data()
                    dat = np.mean(vna_data['amplitude'])
                    print(f"{datetime.now()} {dat} dB")
                    full_data['amplitude'][step_x][step_z] = dat
                    full_data['vna_data'].append(vna_data)
                    self.data.emit(full_data)
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
        f_layout = QFormLayout()
        h_layout = QHBoxLayout()

        self.x_start = DoubleSpinBox(self)
        self.x_start.setRange(-1000, 1000)
        self.x_start.setValue(-10)
        self.x_stop = DoubleSpinBox(self)
        self.x_stop.setRange(-1000, 1000)
        self.x_stop.setValue(-90)
        self.x_points = QSpinBox(self)
        self.x_points.setRange(1, 2000)
        self.x_points.setValue(4)

        self.y_start = DoubleSpinBox(self)
        self.y_start.setRange(-1000, 1000)
        self.y_start.setValue(-60)
        self.y_stop = DoubleSpinBox(self)
        self.y_stop.setRange(-1000, 1000)
        self.y_stop.setValue(-60)
        self.y_points = QSpinBox(self)
        self.y_points.setRange(1, 2000)

        self.z_start = DoubleSpinBox(self)
        self.z_start.setRange(-1000, 1000)
        self.z_start.setValue(70)
        self.z_stop = DoubleSpinBox(self)
        self.z_stop.setRange(-1000, 1000)
        self.z_stop.setValue(90)
        self.z_points = QSpinBox(self)
        self.z_points.setRange(1, 2000)
        self.z_points.setValue(4)

        self.vna_power = DoubleSpinBox(self)
        self.vna_power.setRange(-90, 8)
        self.vna_power.setValue(-90)
        self.vna_start_time = DoubleSpinBox(self)
        self.vna_start_time.setRange(0.001, 10)
        self.vna_stop_time = DoubleSpinBox(self)
        self.vna_stop_time.setRange(0.001, 10)
        self.vna_points = QSpinBox(self)
        self.vna_points.setRange(1, 5000)
        self.vna_points.setValue(100)

        self.btn_start_measure = QPushButton("Start", self)
        self.btn_start_measure.clicked.connect(self.start_measure)

        self.btn_stop_measure = QPushButton("Stop", self)
        self.btn_stop_measure.clicked.connect(self.stop_measure)
        self.btn_stop_measure.setEnabled(False)

        f_layout.addRow("X start", self.x_start)
        f_layout.addRow("X stop", self.x_stop)
        f_layout.addRow("X points", self.x_points)

        f_layout.addRow(HLine(self))

        f_layout.addRow("Y start", self.y_start)
        f_layout.addRow("Y stop", self.y_stop)
        f_layout.addRow("Y points", self.y_points)

        f_layout.addRow(HLine(self))

        f_layout.addRow("Z start", self.z_start)
        f_layout.addRow("Z stop", self.z_stop)
        f_layout.addRow("Z points", self.z_points)

        f_layout.addRow(HLine(self))

        f_layout.addRow("VNA power, dBm", self.vna_power)
        f_layout.addRow("VNA start time, s", self.vna_start_time)
        f_layout.addRow("VNA stop time, s", self.vna_stop_time)
        f_layout.addRow("VNA points", self.vna_points)

        h_layout.addWidget(self.btn_start_measure)
        h_layout.addWidget(self.btn_stop_measure)

        layout.addLayout(f_layout)
        layout.addLayout(h_layout)
        self.setLayout(layout)

    def start_measure(self):
        self.measure_thread = MeasureThread(
            x_range=np.linspace(self.x_start.value(), self.x_stop.value(), self.x_points.value()),
            y_range=np.linspace(self.y_start.value(), self.y_stop.value(), self.y_points.value()),
            z_range=np.linspace(self.z_start.value(), self.z_stop.value(), self.z_points.value()),
            vna_power=self.vna_power.value(),
            vna_start=self.vna_start_time.value(),
            vna_stop=self.vna_stop_time.value(),
            vna_points=self.vna_points,
        )

        self.measure_thread.data.connect(self.parent().parent().parent().update_plot)
        self.measure_thread.finished.connect(lambda: self.btn_start_measure.setEnabled(True))
        self.measure_thread.finished.connect(lambda: self.btn_stop_measure.setEnabled(False))

        State.measure_running = True
        self.measure_thread.start()
        self.btn_start_measure.setEnabled(False)
        self.btn_stop_measure.setEnabled(True)

    def stop_measure(self):
        State.measure_running = False
