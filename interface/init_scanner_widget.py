from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from interface.ui.Button import Button
from store.config import ScannerConfig
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

        self.x_port = QtWidgets.QLineEdit(self)
        self.x_port.setText(ScannerConfig.AXIS_X_PORT)
        self.y_port = QtWidgets.QLineEdit(self)
        self.y_port.setText(ScannerConfig.AXIS_Y_PORT)
        self.z_port = QtWidgets.QLineEdit(self)
        self.z_port.setText(ScannerConfig.AXIS_Z_PORT)

        ports_layout.addWidget(self.x_port_label, 0, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_port_label, 0, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_port_label, 0, 2, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.x_port, 1, 0, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.y_port, 1, 1, alignment=Qt.AlignCenter)
        ports_layout.addWidget(self.z_port, 1, 2, alignment=Qt.AlignCenter)

        self.init_status = QtWidgets.QLabel("Not Initialized yet")
        self.btn_init = Button("Initialize")
        self.btn_init.clicked.connect(self.initialize)

        layout.addLayout(ports_layout)
        layout.addWidget(self.init_status)
        layout.addWidget(self.btn_init)

        self.setLayout(layout)

    def initialize(self):
        ScannerConfig.AXIS_X_PORT = self.x_port.text()
        ScannerConfig.AXIS_Y_PORT = self.y_port.text()
        ScannerConfig.AXIS_Z_PORT = self.z_port.text()
        status = State.init_scanner()
        if status:
            self.init_status.setText("Initialized Successfully")
        else:
            self.init_status.setText("Connection Error!")
