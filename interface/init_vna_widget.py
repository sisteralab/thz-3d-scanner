from PySide6 import QtWidgets
from PySide6.QtCore import QThread, Signal

from interface.ui.Button import Button
from store.state import State


class InitializeThread(QThread):
    status = Signal(bool)

    def run(self):
        status = State.init_vna()
        self.status.emit(status)


class InitVnaWidget(QtWidgets.QGroupBox):
    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Vna init")

        self.initialize_thread: InitializeThread = None

        layout = QtWidgets.QVBoxLayout()
        form_layout = QtWidgets.QFormLayout()

        self.host = QtWidgets.QLineEdit(self)
        self.host.setText(State.vna_host)
        self.port = QtWidgets.QSpinBox(self)
        self.port.setRange(1, 500000)
        self.port.setValue(State.vna_port)

        form_layout.addRow("Host", self.host)
        form_layout.addRow("Port", self.port)

        self.init_status = QtWidgets.QLabel("Not Initialized yet")
        self.btn_init = Button("Initialize", animate=True)
        self.btn_init.clicked.connect(self.initialize)

        layout.addLayout(form_layout)
        layout.addWidget(self.init_status)
        layout.addWidget(self.btn_init)

        self.setLayout(layout)

    def initialize(self):
        # Update state with new VNA configuration
        State.vna_host = self.host.text()
        State.vna_port = self.port.value()

        self.initialize_thread = InitializeThread()

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
