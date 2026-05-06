import logging
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QLabel, QVBoxLayout
from typing import Literal

from interface.ui.Button import Button
from interface.ui.DoubleSpinBox import DoubleSpinBox
from store.state import State
from utils.exceptions import exception_no_devices

logger = logging.getLogger(__name__)


class MonitorThread(QThread):
    positions = Signal(dict)
    log = Signal(dict)

    @staticmethod
    def _read_position(device_id, calibration=None):
        if not device_id:
            return None
        return State.scanner.get_position(device_id, calibration)

    def run(self) -> None:
        try:
            while State.monitor_running:
                x = self._read_position(State.scanner.id_x)
                y = self._read_position(State.scanner.id_y)
                z = self._read_position(State.scanner.id_z)
                rotation = self._read_position(
                    State.scanner.id_rotation,
                    State.scanner.rotation_unit,
                )
                self.positions.emit(
                    {
                        "x": x,
                        "y": y,
                        "z": z,
                        "rotation": rotation,
                    }
                )
                self.msleep(100)
        except (AttributeError, Exception) as e:
            self.log.emit({"type": "error", "msg": f"{e}"})


class MoveThread(QThread):
    log = Signal(dict)

    def __init__(self, axis: Literal["x", "y", "z", "rotation"], position: float):
        super().__init__()
        self.axis = axis
        self.position = position

    def run(self) -> None:
        try:
            method = getattr(State.scanner, f"move_{self.axis}")
            method(self.position)
        except (AttributeError, Exception) as e:
            self.log.emit({"type": "error", "msg": f"{e}"})


class ShiftRotationThread(QThread):
    log = Signal(dict)

    def __init__(self, distance: float):
        super().__init__()
        self.distance = distance

    def run(self) -> None:
        try:
            State.scanner.shift_rotation(self.distance)
        except (AttributeError, Exception) as e:
            self.log.emit({"type": "error", "msg": f"{e}"})


class ScannerPositionMonitorWidget(QGroupBox):
    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Scanner position monitor")

        self.setMaximumHeight(320)

        self.move_thread: Optional[MoveThread] = None
        self.shift_rotation_thread: Optional[ShiftRotationThread] = None
        self.monitor_thread: Optional[MonitorThread] = None

        layout = QVBoxLayout()
        monitor_stream_layout = QGridLayout()
        monitor_buttons_layout = QHBoxLayout()
        set_values_layout = QGridLayout()

        self.x_label = QLabel("X, mm", self)
        self.y_label = QLabel("Y, mm", self)
        self.z_label = QLabel("Z, mm", self)
        self.rotation_label = QLabel("Rotation, deg", self)

        self.x_value = QLabel("None", self)
        self.y_value = QLabel("None", self)
        self.z_value = QLabel("None", self)
        self.rotation_value = QLabel("None", self)

        self.btn_start_monitor = Button("Start monitor", self, animate=True)
        self.btn_start_monitor.clicked.connect(self.start_monitor)
        self.btn_stop_monitor = Button("Stop monitor", self)
        self.btn_stop_monitor.clicked.connect(self.stop_monitor)
        self.btn_stop_monitor.setEnabled(False)

        self.x_value_set = DoubleSpinBox(self, lambda: self.set_x())
        self.x_value_set.setRange(-500, 500)
        self.x_value_set.setDecimals(2)

        self.y_value_set = DoubleSpinBox(self, lambda: self.set_y())
        self.y_value_set.setRange(-500, 500)
        self.y_value_set.setDecimals(2)

        self.z_value_set = DoubleSpinBox(self, lambda: self.set_z())
        self.z_value_set.setRange(-500, 500)
        self.z_value_set.setDecimals(2)

        self.rotation_value_set = DoubleSpinBox(self, lambda: self.set_rotation())
        self.rotation_value_set.setRange(-36000, 36000)
        self.rotation_value_set.setDecimals(3)

        self.rotation_shift_set = DoubleSpinBox(self, lambda: self.shift_rotation())
        self.rotation_shift_set.setRange(-36000, 36000)
        self.rotation_shift_set.setDecimals(3)
        self.rotation_shift_set.setValue(1)

        self.btn_x_set = Button("Move X", self, animate=True)
        self.btn_x_set.clicked.connect(self.set_x)

        self.btn_y_set = Button("Move Y", self, animate=True)
        self.btn_y_set.clicked.connect(self.set_y)

        self.btn_z_set = Button("Move Z", self, animate=True)
        self.btn_z_set.clicked.connect(self.set_z)

        self.btn_rotation_set = Button("Move Rotation", self, animate=True)
        self.btn_rotation_set.clicked.connect(self.set_rotation)

        self.btn_rotation_shift = Button("Shift Rotation", self, animate=True)
        self.btn_rotation_shift.clicked.connect(self.shift_rotation)

        self.btn_x_set_zero = Button("Zero X", self)
        self.btn_x_set_zero.clicked.connect(self.set_x_zero)

        self.btn_y_set_zero = Button("Zero Y", self)
        self.btn_y_set_zero.clicked.connect(self.set_y_zero)

        self.btn_z_set_zero = Button("Zero Z", self)
        self.btn_z_set_zero.clicked.connect(self.set_z_zero)

        self.btn_rotation_set_zero = Button("Zero Rotation", self)
        self.btn_rotation_set_zero.clicked.connect(self.set_rotation_zero)

        self.btn_emergency_stop = Button("Emergency Stop", self)
        self.btn_emergency_stop.clicked.connect(self.emergency_stop)

        monitor_stream_layout.addWidget(self.x_label, 0, 0, alignment=Qt.AlignCenter)
        monitor_stream_layout.addWidget(self.y_label, 0, 1, alignment=Qt.AlignCenter)
        monitor_stream_layout.addWidget(self.z_label, 0, 2, alignment=Qt.AlignCenter)
        monitor_stream_layout.addWidget(
            self.rotation_label, 0, 3, alignment=Qt.AlignCenter
        )
        monitor_stream_layout.addWidget(self.x_value, 1, 0, alignment=Qt.AlignCenter)
        monitor_stream_layout.addWidget(self.y_value, 1, 1, alignment=Qt.AlignCenter)
        monitor_stream_layout.addWidget(self.z_value, 1, 2, alignment=Qt.AlignCenter)
        monitor_stream_layout.addWidget(
            self.rotation_value, 1, 3, alignment=Qt.AlignCenter
        )

        monitor_buttons_layout.addWidget(self.btn_start_monitor)
        monitor_buttons_layout.addWidget(self.btn_stop_monitor)

        set_values_layout.addWidget(self.x_value_set, 0, 0, alignment=Qt.AlignCenter)
        set_values_layout.addWidget(self.y_value_set, 0, 1, alignment=Qt.AlignCenter)
        set_values_layout.addWidget(self.z_value_set, 0, 2, alignment=Qt.AlignCenter)
        set_values_layout.addWidget(
            self.rotation_value_set, 0, 3, alignment=Qt.AlignCenter
        )
        set_values_layout.addWidget(self.btn_x_set, 1, 0, alignment=Qt.AlignCenter)
        set_values_layout.addWidget(self.btn_y_set, 1, 1, alignment=Qt.AlignCenter)
        set_values_layout.addWidget(self.btn_z_set, 1, 2, alignment=Qt.AlignCenter)
        set_values_layout.addWidget(
            self.btn_rotation_set, 1, 3, alignment=Qt.AlignCenter
        )
        set_values_layout.addWidget(self.btn_x_set_zero, 2, 0, alignment=Qt.AlignCenter)
        set_values_layout.addWidget(self.btn_y_set_zero, 2, 1, alignment=Qt.AlignCenter)
        set_values_layout.addWidget(self.btn_z_set_zero, 2, 2, alignment=Qt.AlignCenter)
        set_values_layout.addWidget(
            self.btn_rotation_set_zero, 2, 3, alignment=Qt.AlignCenter
        )
        set_values_layout.addWidget(
            self.rotation_shift_set, 3, 2, alignment=Qt.AlignCenter
        )
        set_values_layout.addWidget(
            self.btn_rotation_shift, 3, 3, alignment=Qt.AlignCenter
        )
        set_values_layout.addWidget(self.btn_emergency_stop, 4, 0, 1, 4)

        layout.addLayout(monitor_stream_layout)
        layout.addLayout(monitor_buttons_layout)
        layout.addLayout(set_values_layout)
        self.setLayout(layout)

    def start_monitor(self):
        if not self.monitor_thread:
            self.monitor_thread = MonitorThread()

        self.btn_start_monitor.set_enabled(False, True)
        self.btn_stop_monitor.setEnabled(True)

        self.monitor_thread.positions.connect(self.update_positions)
        self.monitor_thread.finished.connect(
            lambda: self.btn_stop_monitor.set_enabled(False)
        )
        self.monitor_thread.finished.connect(
            lambda: self.btn_start_monitor.set_enabled(True)
        )
        self.monitor_thread.log.connect(self.set_log)
        State.monitor_running = True
        self.monitor_thread.start()

    def stop_monitor(self):
        State.monitor_running = False

    @staticmethod
    def format_position(position, decimals):
        return "None" if position is None else f"{position:.{decimals}f}"

    def update_positions(self, positions: dict):
        self.x_value.setText(self.format_position(positions.get("x"), 2))
        self.y_value.setText(self.format_position(positions.get("y"), 2))
        self.z_value.setText(self.format_position(positions.get("z"), 2))
        self.rotation_value.setText(self.format_position(positions.get("rotation"), 3))

    @staticmethod
    def axis_is_initialized(axis: Literal["x", "y", "z", "rotation"]) -> bool:
        if not State.scanner:
            return False
        device_id = getattr(State.scanner, f"id_{axis}")
        return bool(device_id)

    def set_position(self, axis: Literal["x", "y", "z", "rotation"]):
        if self.move_thread and self.move_thread.isRunning():
            logger.info("Scanner is moving, wait please")
            return
        if not self.axis_is_initialized(axis):
            logger.error(f"{axis.upper()} axis is not initialized!")
            return

        variable = getattr(self, f"{axis}_value_set")
        self.move_thread = MoveThread(axis=axis, position=variable.value())

        self.btn_x_set.set_enabled(False, animate=axis == "x")
        self.btn_y_set.set_enabled(False, animate=axis == "y")
        self.btn_z_set.set_enabled(False, animate=axis == "z")
        self.btn_rotation_set.set_enabled(False, animate=axis == "rotation")
        self.btn_rotation_shift.set_enabled(False, animate=False)

        self.move_thread.finished.connect(lambda: self.btn_x_set.set_enabled(True))
        self.move_thread.finished.connect(lambda: self.btn_y_set.set_enabled(True))
        self.move_thread.finished.connect(lambda: self.btn_z_set.set_enabled(True))
        self.move_thread.finished.connect(
            lambda: self.btn_rotation_set.set_enabled(True)
        )
        self.move_thread.finished.connect(
            lambda: self.btn_rotation_shift.set_enabled(True)
        )
        self.move_thread.log.connect(self.set_log)

        self.move_thread.start()

    @staticmethod
    def set_log(log: dict):
        log_type = log.get("type")
        if not log_type:
            return
        method = getattr(logger, log_type, None)
        if not method:
            return
        method(log.get("msg"))

    def set_x(self):
        self.set_position(axis="x")

    def set_y(self):
        self.set_position(axis="y")

    def set_z(self):
        self.set_position(axis="z")

    def set_rotation(self):
        self.set_position(axis="rotation")

    @exception_no_devices
    def set_x_zero(self):
        if not self.axis_is_initialized("x"):
            logger.error("X axis is not initialized!")
            return
        State.scanner.set_axis_origin(State.scanner.id_x)

    @exception_no_devices
    def set_y_zero(self):
        if not self.axis_is_initialized("y"):
            logger.error("Y axis is not initialized!")
            return
        State.scanner.set_axis_origin(State.scanner.id_y)

    @exception_no_devices
    def set_z_zero(self):
        if not self.axis_is_initialized("z"):
            logger.error("Z axis is not initialized!")
            return
        State.scanner.set_axis_origin(State.scanner.id_z)

    @exception_no_devices
    def set_rotation_zero(self):
        if not self.axis_is_initialized("rotation"):
            logger.error("Rotation device is not initialized!")
            return
        State.scanner.set_axis_origin(State.scanner.id_rotation)

    @exception_no_devices
    def shift_rotation(self):
        if (
            self.move_thread
            and self.move_thread.isRunning()
            or self.shift_rotation_thread
            and self.shift_rotation_thread.isRunning()
        ):
            logger.info("Scanner is moving, wait please")
            return
        if not self.axis_is_initialized("rotation"):
            logger.error("Rotation device is not initialized!")
            return

        self.shift_rotation_thread = ShiftRotationThread(
            self.rotation_shift_set.value()
        )
        self.btn_rotation_set.set_enabled(False)
        self.btn_rotation_shift.set_enabled(False, animate=True)
        self.shift_rotation_thread.finished.connect(
            lambda: self.btn_rotation_set.set_enabled(True)
        )
        self.shift_rotation_thread.finished.connect(
            lambda: self.btn_rotation_shift.set_enabled(True)
        )
        self.shift_rotation_thread.log.connect(self.set_log)
        self.shift_rotation_thread.start()

    @exception_no_devices
    def emergency_stop(self):
        State.scanner.emergency_stop()
