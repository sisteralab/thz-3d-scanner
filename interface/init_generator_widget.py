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
        # The State initialization methods now use the State configurations,
        # which were updated before this thread was started
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

        # Determine which generator configuration to use based on config.id
        if self.config.id == 1:
            self.host = QtWidgets.QLineEdit(self)
            self.host.setText(State.generator_1_host)
            self.port = QtWidgets.QSpinBox(self)
            self.port.setRange(1, 500000)
            self.port.setValue(State.generator_1_port)
            self.gpib = QtWidgets.QSpinBox(self)
            self.gpib.setRange(1, 32)
            self.gpib.setValue(State.generator_1_gpib)
        else:  # config.id == 2
            self.host = QtWidgets.QLineEdit(self)
            self.host.setText(State.generator_2_host)
            self.port = QtWidgets.QSpinBox(self)
            self.port.setRange(1, 500000)
            self.port.setValue(State.generator_2_port)
            self.gpib = QtWidgets.QSpinBox(self)
            self.gpib.setRange(1, 32)
            self.gpib.setValue(State.generator_2_gpib)

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
        # Update the appropriate generator configuration in State
        if self.config.id == 1:
            State.generator_1_host = self.host.text()
            State.generator_1_port = self.port.value()
            State.generator_1_gpib = self.gpib.value()
        else:  # config.id == 2
            State.generator_2_host = self.host.text()
            State.generator_2_port = self.port.value()
            State.generator_2_gpib = self.gpib.value()

        self.initialize_thread = InitializeThread(config=self.config)

        self.initialize_thread.finished.connect(lambda: self.btn_init.set_enabled(True))
        self.initialize_thread.status.connect(self.set_status)

        self.initialize_thread.start()
        self.btn_init.set_enabled(False)

    def set_status(self, status: bool):
        if status:
            self.init_status.setText("Initialized Successfully")
            State.store_state()  # Save the new configuration
        else:
            self.init_status.setText("Connection Error!")
