from PySide6.QtWidgets import QWidget, QVBoxLayout

from interface.measure_widget import MeasureWidget
from interface.monitor_widget import MonitorWidget


class ManagerWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.setMaximumWidth(300)
        layout = QVBoxLayout()

        layout.addWidget(MonitorWidget(self))
        layout.addWidget(MeasureWidget(self))

        self.setLayout(layout)
