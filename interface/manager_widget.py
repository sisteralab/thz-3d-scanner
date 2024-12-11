from PySide6.QtWidgets import QVBoxLayout, QWidget

from interface.measure_widget import MeasureWidget
from interface.scanner_position_monitor_widget import ScannerPositionMonitorWidget


class ManagerWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.setMaximumWidth(300)
        layout = QVBoxLayout()

        layout.addWidget(ScannerPositionMonitorWidget(self))
        layout.addWidget(MeasureWidget(self))

        self.setLayout(layout)
