import logging

from PySide6 import QtGui
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QApplication,
)

from interface.log import LogHandler, LogWidget
from interface.manager_widget import ManagerWidget
from interface.plot_widgets import (
    AmplitudePlotWidget,
    PhasePlotWidget,
)
from store.state import State


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scanner 3D")
        self.setGeometry(100, 100, 1200, 600)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QHBoxLayout(self.central_widget)
        left_layout = QVBoxLayout()

        self.manager_widget = ManagerWidget(self)

        # Create amplitude pyqtgraph widget
        self.amplitude_widget = AmplitudePlotWidget()

        # Create phase pyqtgraph widget
        self.phase_widget = PhasePlotWidget()

        self.log_widget = LogWidget(self)

        # Create a horizontal layout for both plots
        plots_layout = QHBoxLayout()
        plots_layout.addWidget(self.amplitude_widget, stretch=1)
        plots_layout.addWidget(self.phase_widget, stretch=1)

        left_layout.addLayout(plots_layout)
        left_layout.addWidget(self.log_widget)

        self.layout.addLayout(
            left_layout, stretch=2
        )  # Give more space to plot/log area
        self.layout.addWidget(
            self.manager_widget, stretch=1
        )  # Give reasonable space to manager

        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        log_widget_handler = LogHandler(self.log_widget)
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        log_widget_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        logger.addHandler(log_widget_handler)
        logger.addHandler(stream_handler)

        # Initialize with default data
        self.update_plot(
            {
                "amplitude": [
                    [-2, -1, 0, 1],
                    [-2, -1, 0, 1],
                    [-2, -1, 0, 1],
                    [-2, -1, 0, 1],
                    [-2, -1, 0, 1],
                ],
                "phase": [
                    [0, 45, 90, 135],
                    [180, 225, 270, 315],
                    [360, 405, 450, 495],
                    [540, 585, 630, 675],
                    [720, 765, 810, 855],
                ],
                "x": [-20, -10, 10, 20, 30],
                "z": [-20, -10, 10, 20],
            }
        )

    def update_plot(self, data):
        """Update the visualization with new measurement data"""
        self.amplitude_widget.update_data(data)
        self.phase_widget.update_data(data)

    def closeEvent(self, event: QtGui.QCloseEvent):
        State.del_scanner()
        State.del_vna()
        State.store_state()
        for window in QApplication.topLevelWidgets():
            window.close()
        event.accept()
