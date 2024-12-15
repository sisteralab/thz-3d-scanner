from PySide6.QtWidgets import QVBoxLayout, QWidget

from interface.init_scanner_widget import InitScannerWidget
from interface.init_vna_widget import InitVnaWidget
from interface.measure_widget import MeasureWidget
from interface.scanner_position_monitor_widget import ScannerPositionMonitorWidget


class ManagerWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.setMaximumWidth(300)
        layout = QVBoxLayout()

        layout.addWidget(InitScannerWidget(self))
        layout.addWidget(InitVnaWidget(self))
        layout.addWidget(ScannerPositionMonitorWidget(self))
        layout.addWidget(MeasureWidget(self))

        self.setLayout(layout)
