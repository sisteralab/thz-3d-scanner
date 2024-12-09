from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QGridLayout, QHBoxLayout, QLabel, QPushButton

from store.state import State


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
