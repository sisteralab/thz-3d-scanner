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
    QCheckBox,
)

from interface.log import LogHandler, LogWidget
from interface.memory_monitor import MemoryMonitor
from interface.manager_widget import ManagerWidget
from interface.plot_widgets import (
    AmplitudePlotWidget,
    ComplexReferenceController,
    ComplexReferenceWidget,
    PhasePlotWidget,
    RotationSliceSelectorWidget,
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
        self._current_rotation_index = 0

        # Create amplitude pyqtgraph widget
        self.amplitude_widget = AmplitudePlotWidget(
            reference_controller=self.reference_controller
        )

        # Create phase pyqtgraph widget
        self.phase_widget = PhasePlotWidget(
            reference_controller=self.reference_controller
        )
        self.reference_widget = ComplexReferenceWidget(self.reference_controller)
        self.rotation_slice_widget = RotationSliceSelectorWidget()
        self.y_slice_widget = YSliceSelectorWidget()
        self.show_late_samples_checkbox = QCheckBox("Show late samples", self)
        self.show_late_samples_checkbox.setChecked(True)
        self.show_late_samples_checkbox.setToolTip(
            "Show points measured after the scanner already passed their target."
        )
        self.reference_controller.corrected_data_ready.connect(
            self._apply_corrected_data
        )
        self.rotation_slice_widget.rotation_index_changed.connect(
            self._on_rotation_slice_changed
        )
        self.y_slice_widget.y_index_changed.connect(self._on_y_slice_changed)
        self.show_late_samples_checkbox.toggled.connect(
            self._set_late_sample_markers_visible
        )

        self.log_widget = LogWidget(self)
        self.memory_monitor = MemoryMonitor(self)

        # Create a horizontal layout for both plots
        plots_layout = QHBoxLayout()
        plots_layout.addWidget(self.amplitude_widget, stretch=1)
        plots_layout.addWidget(self.phase_widget, stretch=1)

        left_layout.addWidget(self.rotation_slice_widget)
        left_layout.addWidget(self.y_slice_widget)
        left_layout.addWidget(self.show_late_samples_checkbox)
        left_layout.addWidget(self.reference_widget)
        left_layout.addLayout(plots_layout)
        left_layout.addWidget(self.log_widget)
        left_layout.addWidget(self.memory_monitor)

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

        data = np.random.normal(size=(200, 100)).astype(np.float32)
        data[20:80, 20:80] += 2.0
        data = pg.gaussianFilter(data, (3, 3)).astype(np.float32)
        data += np.random.normal(size=(200, 100)).astype(np.float32) * 0.1

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
        # Clean up heavy raw data to reduce RAM usage
        if isinstance(data, dict) and "vna_data" in data:
            data = {k: v for k, v in data.items() if k != "vna_data"}
        self._source_data = data
        rotation_axis = self._extract_rotation_axis(data)
        self.rotation_slice_widget.set_rotation_values(rotation_axis)
        self._current_rotation_index = int(
            np.clip(self._current_rotation_index, 0, rotation_axis.size - 1)
        )
        self.rotation_slice_widget.set_index(
            self._current_rotation_index,
            emit_signal=False,
        )
        current_data = self._current_rotation_data()
        y_axis = self._extract_y_axis(current_data)
        self.y_slice_widget.set_y_values(y_axis)
        self._current_y_index = int(np.clip(self._current_y_index, 0, y_axis.size - 1))
        self.y_slice_widget.set_index(self._current_y_index, emit_signal=False)
        self._push_current_slice()

    @staticmethod
    def _extract_y_axis(data):
        if not isinstance(data, dict):
            return np.array([0.0], dtype=float)
        amplitude = np.asarray(data.get("amplitude", []))
        if amplitude.ndim != 3:
            return np.array([0.0], dtype=float)
        y_len = amplitude.shape[0]
        y_axis = np.asarray(data.get("y", np.arange(y_len)), dtype=float)
        if y_axis.size != y_len:
            y_axis = np.arange(y_len, dtype=float)
        return y_axis

    @staticmethod
    def _extract_rotation_axis(data):
        if isinstance(data, list):
            values = []
            for item in data:
                if isinstance(item, dict):
                    values.append(float(item.get("rotation_angle", 0.0)))
            if values:
                return np.asarray(values, dtype=float)
        if isinstance(data, dict) and "rotation_angle" in data:
            return np.asarray([float(data.get("rotation_angle", 0.0))], dtype=float)
        return np.array([0.0], dtype=float)

    def _current_rotation_data(self):
        if isinstance(self._source_data, list):
            if not self._source_data:
                return {}
            idx = int(
                np.clip(
                    self._current_rotation_index,
                    0,
                    len(self._source_data) - 1,
                )
            )
            return self._source_data[idx]
        return self._source_data

    def _on_rotation_slice_changed(self, rotation_index):
        self._current_rotation_index = int(rotation_index)
        current_data = self._current_rotation_data()
        y_axis = self._extract_y_axis(current_data)
        self.y_slice_widget.set_y_values(y_axis)
        self._current_y_index = int(np.clip(self._current_y_index, 0, y_axis.size - 1))
        self.y_slice_widget.set_index(self._current_y_index, emit_signal=False)
        self._push_current_slice()

    def _on_y_slice_changed(self, y_index):
        self._current_y_index = int(y_index)
        self._push_current_slice()

    def _push_current_slice(self):
        if self._source_data is None:
            return
        self.reference_controller.set_raw_data(
            extract_xz_slice(self._current_rotation_data(), self._current_y_index)
        )

    def _apply_corrected_data(self, data):
        """Apply corrected data after complex reference subtraction."""
        self.amplitude_widget.update_data(data)
        self.phase_widget.update_data(data)

    def _set_late_sample_markers_visible(self, visible):
        self.amplitude_widget.set_late_sample_markers_visible(visible)
        self.phase_widget.set_late_sample_markers_visible(visible)

    def closeEvent(self, event: QtGui.QCloseEvent):
        State.del_scanner()
        State.del_vna()
        State.store_state()
        for window in QApplication.topLevelWidgets():
            window.close()
        event.accept()
