import sys

import numpy as np
import pyqtgraph.opengl as gl
from PySide6 import QtGui
from PySide6.QtWidgets import QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, QWidget, QFormLayout, QDoubleSpinBox, \
    QSpinBox, QPushButton, QGroupBox, QGridLayout, QLabel
from PySide6.QtCore import QThread, Signal

from api.commands import Commands
from api.vna import VNABlock


class State:
    measure_running = False
    d3 = None
    vna = None

    @classmethod
    def init_d3(cls):
        cls.d3 = Commands()
        cls.d3.connect_devices()
        cls.d3.set_units()

    @classmethod
    def init_vna(cls):
        cls.vna = VNABlock()

    @classmethod
    def del_d3(cls):
        cls.d3.disconnect_devices()
        del cls.d3

    @classmethod
    def del_vna(cls):
        del cls.vna


class MeasureThread(QThread):
    data = Signal(dict)

    def __init__(
        self,
        x_range,
        y_range,
        z_range,
        # vna_parameter,
        # vna_power,
        # vna_start,
        # vna_stop,
        # vna_points
    ):
        super().__init__()
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
        # self.vna_parameter = vna_parameter
        # self.vna_power = vna_power
        # self.vna_start = vna_start
        # self.vna_stop = vna_stop
        # self.vna_points = vna_points

        self.init_x = State.d3.get_position(State.d3.id_x)
        self.init_y = State.d3.get_position(State.d3.id_y)
        self.init_z = State.d3.get_position(State.d3.id_z)

    def run(self):
        # State.vna.set_parameter(self.vna_parameter)
        # State.vna.set_start_frequency(self.vna_start)
        # State.vna.set_stop_frequency(self.vna_stop)
        # State.vna.set_sweep(self.vna_points)
        # State.vna.set_power(self.vna_power)
        # State.vna.set_channel_format("COMP")
        # State.vna.set_average_count(10)
        # State.vna.set_average_status(True)

        while State.measure_running:

            z = np.sin(np.sqrt(self.x[:, np.newaxis]**2 + self.y[np.newaxis, :]**2 + np.random.rand() * 10))
            self.data.emit({"x": self.x, "y": self.y, "z": z})
            self.msleep(100)


class MonitorWidget(QGroupBox):
    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Monitor")

        self.setMaximumHeight(100)

        layout = QVBoxLayout()
        g_layout = QGridLayout()
        h_layout = QHBoxLayout()

        self.x_label = QLabel("X", self)
        self.y_label = QLabel("Y", self)
        self.z_label = QLabel("Z", self)

        self.x_value = QLabel("None", self)
        self.y_value = QLabel("None", self)
        self.z_value = QLabel("None", self)

        self.btn_update = QPushButton("Update position", self)
        self.btn_update.clicked.connect(self.update_position)

        g_layout.addWidget(self.x_label, 0, 0)
        g_layout.addWidget(self.y_label, 0, 1)
        g_layout.addWidget(self.z_label, 0, 2)
        g_layout.addWidget(self.x_value, 1, 0)
        g_layout.addWidget(self.y_value, 1, 1)
        g_layout.addWidget(self.z_value, 1, 2)

        h_layout.addWidget(self.btn_update)

        layout.addLayout(g_layout)
        layout.addLayout(h_layout)
        self.setLayout(layout)

    def update_position(self):
        x = State.d3.get_position(State.d3.id_x)
        y = State.d3.get_position(State.d3.id_y)
        z = State.d3.get_position(State.d3.id_z)
        self.x_value.setText(f"{x:.4}")
        self.y_value.setText(f"{y:.4}")
        self.z_value.setText(f"{z:.4}")


class MeasureWidget(QGroupBox):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle("Measure")

        self.measure_thread = None

        layout = QVBoxLayout()
        f_layout = QFormLayout()
        h_layout = QHBoxLayout()

        self.x_start = QDoubleSpinBox(self)
        self.x_start.setRange(-1000, 1000)
        self.x_stop = QDoubleSpinBox(self)
        self.x_stop.setRange(-1000, 1000)
        self.x_points = QSpinBox(self)
        self.x_points.setRange(1, 2000)

        self.y_start = QDoubleSpinBox(self)
        self.y_start.setRange(-1000, 1000)
        self.y_stop = QDoubleSpinBox(self)
        self.y_stop.setRange(-1000, 1000)
        self.y_points = QSpinBox(self)
        self.y_points.setRange(1, 2000)

        self.z_start = QDoubleSpinBox(self)
        self.z_start.setRange(-1000, 1000)
        self.z_stop = QDoubleSpinBox(self)
        self.z_stop.setRange(-1000, 1000)
        self.z_points = QSpinBox(self)
        self.z_points.setRange(1, 2000)

        # self.vna_start_freq = QDoubleSpinBox(self)
        # self.vna_start_freq.setRange(0.01, 60)
        # self.vna_stop_freq = QDoubleSpinBox(self)
        # self.vna_stop_freq.setRange(0.01, 60)
        # self.vna_points = QSpinBox(self)
        # self.vna_points.setRange(1, 5000)

        self.btn_start_measure = QPushButton("Start", self)
        self.btn_start_measure.clicked.connect(self.start_measure)

        self.btn_stop_measure = QPushButton("Stop", self)
        self.btn_stop_measure.clicked.connect(self.stop_measure)
        self.btn_stop_measure.setEnabled(False)

        f_layout.addRow("X start", self.x_start)
        f_layout.addRow("X stop", self.x_stop)
        f_layout.addRow("X points", self.x_points)

        f_layout.addRow("Y start", self.y_start)
        f_layout.addRow("Y stop", self.y_stop)
        f_layout.addRow("Y points", self.y_points)

        f_layout.addRow("Z start", self.z_start)
        f_layout.addRow("Z stop", self.z_stop)
        f_layout.addRow("Z points", self.z_points)

        # f_layout.addRow("VNA start freq, GHz", self.vna_start_freq)
        # f_layout.addRow("VNA stop freq, GHz", self.vna_stop_freq)
        # f_layout.addRow("VNA points", self.vna_points)

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


class ManagerWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.setMaximumWidth(300)
        layout = QVBoxLayout()

        layout.addWidget(MonitorWidget(self))
        layout.addWidget(MeasureWidget(self))

        self.setLayout(layout)


class Scanner3D(QMainWindow):
    def __init__(self):
        super().__init__()
        State.init_d3()
        # State.init_vna()
        self.setWindowTitle("Scanner 3D")
        self.setGeometry(100, 100, 1200, 600)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QHBoxLayout(self.central_widget)

        self.manager_widget = ManagerWidget(self)
        self.plot_widget = gl.GLViewWidget()

        self.layout.addWidget(self.plot_widget)
        self.layout.addWidget(self.manager_widget)

        # preparing plot
        self.plot_item = gl.GLSurfacePlotItem(shader='heightColor', computeNormals=False, smooth=False)
        self.plot_widget.addItem(self.plot_item)
        self.prepare_plot()

    def prepare_plot(self):
        # Добавление сетки
        self.grid = gl.GLGridItem()
        self.plot_widget.addItem(self.grid)

        # Добавление подписей к осям
        self.x_label = gl.GLTextItem(pos=(10, 0, 0), text='X')
        self.y_label = gl.GLTextItem(pos=(0, 10, 0), text='Y')
        self.z_label = gl.GLTextItem(pos=(0, 0, 10), text='Z')
        self.plot_widget.addItem(self.x_label)
        self.plot_widget.addItem(self.y_label)
        self.plot_widget.addItem(self.z_label)

    def update_plot(self, data):
        self.plot_item.setData(x=data['x'], y=data['y'], z=data['z'])

    def closeEvent(self, event: QtGui.QCloseEvent):
        State.del_d3()
        State.del_vna()
        event.accept()
