from PySide6 import QtWidgets
from PySide6.QtWidgets import QDoubleSpinBox
from PySide6.QtCore import Qt

from interface.ui.Button import Button
from store.state import State


class InitScannerWidget(QtWidgets.QGroupBox):
    def __init__(self, parent):
        super().__init__(parent)

        self.setTitle("Scanner Init")

        layout = QtWidgets.QVBoxLayout()
        ports_layout = QtWidgets.QGridLayout()

        self.x_port_label = QtWidgets.QLabel("X port", self)
        self.y_port_label = QtWidgets.QLabel("Y port", self)
        self.z_port_label = QtWidgets.QLabel("Z port", self)
        self.rotation_port_label = QtWidgets.QLabel("Rotation port", self)

        self.x_port = QtWidgets.QLineEdit(self)
        self.x_port.setText(State.scanner_x_port)
        self.y_port = QtWidgets.QLineEdit(self)
        self.y_port.setText(State.scanner_y_port)
        self.z_port = QtWidgets.QLineEdit(self)
        self.z_port.setText(State.scanner_z_port)
        self.rotation_port = QtWidgets.QLineEdit(self)
        self.rotation_port.setText(State.scanner_rotation_port)
        self.rotation_degrees_per_step = QDoubleSpinBox(self)
        self.rotation_degrees_per_step.setRange(0.000001, 360)
        self.rotation_degrees_per_step.setDecimals(6)
        self.rotation_degrees_per_step.setValue(State.scanner_rotation_degrees_per_step)
        self.rotation_degrees_per_step.setToolTip("Rotation calibration, deg/step")
        self.rotation_degrees_per_step.setMinimumWidth(95)

        self.x_distance_per_step = self._scale_spin_box(
            State.scanner_x_distance_per_step,
            "X scale factor, mm/step",
        )
        self.y_distance_per_step = self._scale_spin_box(
            State.scanner_y_distance_per_step,
            "Y scale factor, mm/step",
        )
        self.z_distance_per_step = self._scale_spin_box(
            State.scanner_z_distance_per_step,
            "Z scale factor, mm/step",
        )

        self.x_speed = self._movement_spin_box(
            State.scanner_x_speed,
            "X speed, mm/s",
        )
        self.x_accel = self._movement_spin_box(
            State.scanner_x_accel,
            "X acceleration, mm/s^2",
        )
        self.x_decel = self._movement_spin_box(
            State.scanner_x_decel,
            "X deceleration, mm/s^2",
        )
        self.y_speed = self._movement_spin_box(
            State.scanner_y_speed,
            "Y speed, mm/s",
        )
        self.y_accel = self._movement_spin_box(
            State.scanner_y_accel,
            "Y acceleration, mm/s^2",
        )
        self.y_decel = self._movement_spin_box(
            State.scanner_y_decel,
            "Y deceleration, mm/s^2",
        )
        self.z_speed = self._movement_spin_box(
            State.scanner_z_speed,
            "Z speed, mm/s",
        )
        self.z_accel = self._movement_spin_box(
            State.scanner_z_accel,
            "Z acceleration, mm/s^2",
        )
        self.z_decel = self._movement_spin_box(
            State.scanner_z_decel,
            "Z deceleration, mm/s^2",
        )
        self.rotation_speed = self._movement_spin_box(
            State.scanner_rotation_speed,
            "Rotation speed, deg/s",
        )
        self.rotation_accel = self._movement_spin_box(
            State.scanner_rotation_accel,
            "Rotation acceleration, deg/s^2",
        )
        self.rotation_decel = self._movement_spin_box(
            State.scanner_rotation_decel,
            "Rotation deceleration, deg/s^2",
        )

        ports_layout.addWidget(self.x_port_label, 0, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_port_label, 0, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_port_label, 0, 2, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.rotation_port_label, 0, 3, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.x_port, 1, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_port, 1, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_port, 1, 2, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.rotation_port, 1, 3, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.x_speed, 2, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_speed, 2, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_speed, 2, 2, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.rotation_speed, 2, 3, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.x_accel, 3, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_accel, 3, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_accel, 3, 2, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.rotation_accel, 3, 3, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.x_decel, 4, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_decel, 4, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_decel, 4, 2, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.rotation_decel, 4, 3, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.x_distance_per_step, 5, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_distance_per_step, 5, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_distance_per_step, 5, 2, alignment=Qt.AlignCenter)
        ports_layout.addWidget(
            self.rotation_degrees_per_step, 5, 3, alignment=Qt.AlignCenter
        )

        self.init_status = QtWidgets.QLabel("Not Initialized yet")
        self.btn_init = Button("Initialize")
        self.btn_init.clicked.connect(self.initialize)

        layout.addLayout(ports_layout)
        layout.addWidget(self.init_status)
        layout.addWidget(self.btn_init)

        self.setLayout(layout)

    def _movement_spin_box(self, value, tooltip):
        spin_box = QDoubleSpinBox(self)
        spin_box.setRange(0.000001, 1000000)
        spin_box.setDecimals(4)
        spin_box.setValue(value)
        spin_box.setToolTip(tooltip)
        spin_box.setMinimumWidth(95)
        return spin_box

    def _scale_spin_box(self, value, tooltip):
        spin_box = QDoubleSpinBox(self)
        spin_box.setRange(0.000000001, 1000000)
        spin_box.setDecimals(9)
        spin_box.setValue(value)
        spin_box.setToolTip(tooltip)
        spin_box.setMinimumWidth(95)
        return spin_box

    def initialize(self):
        # Update state with new port configurations
        State.scanner_x_port = self.x_port.text()
        State.scanner_y_port = self.y_port.text()
        State.scanner_z_port = self.z_port.text()
        State.scanner_rotation_port = self.rotation_port.text()
        State.scanner_x_distance_per_step = self.x_distance_per_step.value()
        State.scanner_y_distance_per_step = self.y_distance_per_step.value()
        State.scanner_z_distance_per_step = self.z_distance_per_step.value()
        State.scanner_rotation_degrees_per_step = self.rotation_degrees_per_step.value()
        State.scanner_x_speed = self.x_speed.value()
        State.scanner_x_accel = self.x_accel.value()
        State.scanner_x_decel = self.x_decel.value()
        State.scanner_y_speed = self.y_speed.value()
        State.scanner_y_accel = self.y_accel.value()
        State.scanner_y_decel = self.y_decel.value()
        State.scanner_z_speed = self.z_speed.value()
        State.scanner_z_accel = self.z_accel.value()
        State.scanner_z_decel = self.z_decel.value()
        State.scanner_rotation_speed = self.rotation_speed.value()
        State.scanner_rotation_accel = self.rotation_accel.value()
        State.scanner_rotation_decel = self.rotation_decel.value()

        status = State.init_scanner()
        if status:
            axes = ", ".join(State.scanner.connected_axes())
            self.init_status.setText(f"Initialized: {axes}")
            State.store_state()  # Save the new configuration
        else:
            self.init_status.setText("Connection Error: no axes initialized")
