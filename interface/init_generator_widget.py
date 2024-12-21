from PySide6 import QtWidgets
from PySide6.QtCore import QThread, Signal
from typing import Optional

from interface.ui.Button import Button
from store.state import State


class InitializeThread(QThread):
    status = Signal(bool)

    def __init__(self, config):
        super().__init__()
        self.config = config

    def run(self):
        method = getattr(State, f"init_generator_{self.config.id}")
        status = method()
        self.status.emit(status)


class InitGeneratorWidget(QtWidgets.QGroupBox):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setTitle(f"Generator {config.id} init")

        self.initialize_thread: Optional[InitializeThread] = None

        self.config = config

        layout = QtWidgets.QVBoxLayout()
        form_layout = QtWidgets.QFormLayout()

        self.host = QtWidgets.QLineEdit(self)
        self.host.setText(self.config.HOST)
        self.port = QtWidgets.QSpinBox(self)
        self.port.setRange(1, 500000)
        self.port.setValue(self.config.PORT)
        self.gpib = QtWidgets.QSpinBox(self)
        self.gpib.setRange(1, 32)
        self.gpib.setValue(self.config.GPIB)

        form_layout.addRow("Host", self.host)
        form_layout.addRow("Port", self.port)
        form_layout.addRow("GPIB", self.gpib)

        self.init_status = QtWidgets.QLabel("Not Initialized yet")
        self.btn_init = Button("Initialize", animate=True)
        self.btn_init.clicked.connect(self.initialize)

        layout.addLayout(form_layout)
        layout.addWidget(self.init_status)
        layout.addWidget(self.btn_init)

        self.setLayout(layout)

    def initialize(self):
        self.config.HOST = self.host.text()
        self.config.PORT = self.port.value()
        self.config.GPIB = self.gpib.value()
        self.initialize_thread = InitializeThread(config=self.config)

        self.initialize_thread.finished.connect(lambda: self.btn_init.set_enabled(True))
        self.initialize_thread.status.connect(self.set_status)

        self.initialize_thread.start()
        self.btn_init.set_enabled(False)

    def set_status(self, status: bool):
        if status:
            self.init_status.setText("Initialized Successfully")
        else:
            self.init_status.setText("Connection Error!")
