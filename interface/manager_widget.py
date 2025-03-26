from PySide6.QtWidgets import QVBoxLayout, QWidget, QTabWidget, QScrollArea

from interface.data_table import DataTable
from interface.init_generator_widget import InitGeneratorWidget
from interface.init_scanner_widget import InitScannerWidget
from interface.init_vna_widget import InitVnaWidget
from interface.measure_widget import MeasureWidget
from interface.scanner_position_monitor_widget import ScannerPositionMonitorWidget
from store.config import SignalGeneratorConfig1, SignalGeneratorConfig2


class ManagerWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.setMaximumWidth(400)

        # Create a tab widget
        tab_widget = QTabWidget(self)

        # Create the Setup tab
        setup_tab = QWidget(tab_widget)
        setup_layout = QVBoxLayout(setup_tab)

        setup_layout.addWidget(InitScannerWidget(self))
        setup_layout.addWidget(InitVnaWidget(self))
        setup_layout.addWidget(InitGeneratorWidget(self, config=SignalGeneratorConfig1))
        setup_layout.addWidget(InitGeneratorWidget(self, config=SignalGeneratorConfig2))

        # Create a scroll area for the Setup tab
        setup_scroll_area = QScrollArea()
        setup_scroll_area.setWidgetResizable(True)
        setup_scroll_area.setWidget(setup_tab)

        # Create the Measure tab
        measure_tab = QWidget(tab_widget)
        measure_layout = QVBoxLayout(measure_tab)

        measure_layout.addWidget(ScannerPositionMonitorWidget(self))
        measure_layout.addWidget(MeasureWidget(self))

        # Create a scroll area for the Measure tab
        measure_scroll_area = QScrollArea()
        measure_scroll_area.setWidgetResizable(True)
        measure_scroll_area.setWidget(measure_tab)

        # Create the Data tab
        data_tab = DataTable()

        # Add tabs to the tab widget
        tab_widget.addTab(setup_scroll_area, "Setup")
        tab_widget.addTab(measure_scroll_area, "Measure")
        tab_widget.addTab(data_tab, "Data")

        # Set the tab widget as the main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(tab_widget)

        self.setLayout(main_layout)
