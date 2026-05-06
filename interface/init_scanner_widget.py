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
        self.rotation_calibration_label = QtWidgets.QLabel("Rotation deg/step", self)

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

        ports_layout.addWidget(self.x_port_label, 0, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_port_label, 0, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_port_label, 0, 2, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.rotation_port_label, 0, 3, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.x_port, 1, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_port, 1, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_port, 1, 2, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.rotation_port, 1, 3, alignment=Qt.AlignCenter)
        ports_layout.addWidget(
            self.rotation_calibration_label, 2, 0, alignment=Qt.AlignCenter
        )
        ports_layout.addWidget(
            self.rotation_degrees_per_step, 2, 1, alignment=Qt.AlignCenter
        )

        self.init_status = QtWidgets.QLabel("Not Initialized yet")
        self.btn_init = Button("Initialize")
        self.btn_init.clicked.connect(self.initialize)

        layout.addLayout(ports_layout)
        layout.addWidget(self.init_status)
        layout.addWidget(self.btn_init)

        self.setLayout(layout)

    def initialize(self):
        # Update state with new port configurations
        State.scanner_x_port = self.x_port.text()
        State.scanner_y_port = self.y_port.text()
        State.scanner_z_port = self.z_port.text()
        State.scanner_rotation_port = self.rotation_port.text()
        State.scanner_rotation_degrees_per_step = self.rotation_degrees_per_step.value()

        status = State.init_scanner()
        if status:
            axes = ", ".join(State.scanner.connected_axes())
            self.init_status.setText(f"Initialized: {axes}")
            State.store_state()  # Save the new configuration
        else:
            self.init_status.setText("Connection Error: no axes initialized")
