import logging

import numpy as np
import pyqtgraph as pg
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
    ComplexReferenceController,
    ComplexReferenceWidget,
    PhasePlotWidget,
    YSliceSelectorWidget,
    extract_xz_slice,
)
from store.state import State


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scanner 3D")
        self.setGeometry(100, 100, 1500, 600)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QHBoxLayout(self.central_widget)
        left_layout = QVBoxLayout()

        self.manager_widget = ManagerWidget(self)
        self.reference_controller = ComplexReferenceController(self)
        self._source_data = None
        self._current_y_index = 0

        # Create amplitude pyqtgraph widget
        self.amplitude_widget = AmplitudePlotWidget(
            reference_controller=self.reference_controller
        )

        # Create phase pyqtgraph widget
        self.phase_widget = PhasePlotWidget(reference_controller=self.reference_controller)
        self.reference_widget = ComplexReferenceWidget(self.reference_controller)
        self.y_slice_widget = YSliceSelectorWidget()
        self.reference_controller.corrected_data_ready.connect(self._apply_corrected_data)
        self.y_slice_widget.y_index_changed.connect(self._on_y_slice_changed)

        self.log_widget = LogWidget(self)

        # Create a horizontal layout for both plots
        plots_layout = QHBoxLayout()
        plots_layout.addWidget(self.amplitude_widget, stretch=1)
        plots_layout.addWidget(self.phase_widget, stretch=1)

        left_layout.addWidget(self.y_slice_widget)
        left_layout.addWidget(self.reference_widget)
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

        data = np.random.normal(size=(200, 100))
        data[20:80, 20:80] += 2.0
        data = pg.gaussianFilter(data, (3, 3))
        data += np.random.normal(size=(200, 100)) * 0.1

        self.update_plot(
            {
                "amplitude": data,
                "phase": data,
                "x": np.linspace(-10, 10, 200),
                "z": np.linspace(-5, 5, 100),
            }
        )

    def update_plot(self, data):
        """Update the visualization with new measurement data"""
        self._source_data = data
        y_axis = self._extract_y_axis(data)
        self.y_slice_widget.set_y_values(y_axis)
        self._current_y_index = int(np.clip(self._current_y_index, 0, y_axis.size - 1))
        self.y_slice_widget.set_index(self._current_y_index, emit_signal=False)
        self._push_current_slice()

    @staticmethod
    def _extract_y_axis(data):
        amplitude = np.asarray(data.get("amplitude", []))
        if amplitude.ndim != 3:
            return np.array([0.0], dtype=float)
        y_len = amplitude.shape[0]
        y_axis = np.asarray(data.get("y", np.arange(y_len)), dtype=float)
        if y_axis.size != y_len:
            y_axis = np.arange(y_len, dtype=float)
        return y_axis

    def _on_y_slice_changed(self, y_index):
        self._current_y_index = int(y_index)
        self._push_current_slice()

    def _push_current_slice(self):
        if self._source_data is None:
            return
        self.reference_controller.set_raw_data(
            extract_xz_slice(self._source_data, self._current_y_index)
        )

    def _apply_corrected_data(self, data):
        """Apply corrected data after complex reference subtraction."""
        self.amplitude_widget.update_data(data)
        self.phase_widget.update_data(data)

    def closeEvent(self, event: QtGui.QCloseEvent):
        State.del_scanner()
        State.del_vna()
        State.store_state()
        for window in QApplication.topLevelWidgets():
            window.close()
        event.accept()
