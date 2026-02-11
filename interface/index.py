import logging

import numpy as np
import pyqtgraph as pg
from PySide6 import QtGui
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget, QVBoxLayout

from interface.log import LogHandler, LogWidget
from interface.manager_widget import ManagerWidget
from store.state import State


class HoverImageItem(pg.ImageItem):
    """Custom ImageItem with hover functionality to show values"""

    def __init__(self, *args, title="Base", **kwargs):
        super().__init__(*args, **kwargs)
        self.plot_item = None
        self.title = title

    def setParentItem(self, parent):
        super().setParentItem(parent)
        if parent is not None:
            parent.scene().sigMouseMoved.connect(self.mouse_moved)

    def setPlotItem(self, plot_item):
        self.plot_item = plot_item

    def mouse_moved(self, pos):
        if self.image is None or self.plot_item is None:
            return

        # Convert scene position to image coordinates (similar to example)
        pos = self.mapFromScene(pos)

        # Get image coordinates
        img_pos = self.mapFromItem(self, pos)
        x = int(img_pos.x())
        y = int(img_pos.y())

        # Check if coordinates are within image bounds (similar to example)
        if 0 <= x < self.image.shape[0] and 0 <= y < self.image.shape[1]:
            value = self.image[x, y]

            # Get real world coordinates
            scene_pos = self.mapToParent(pos)
            x_world = scene_pos.x()
            y_world = scene_pos.y()

            # Update plot title with hover information (similar to example format)
            self.plot_item.setTitle(
                f"X: {x_world:.1f} mm, Z: {y_world:.1f} mm, {self.title}: {value:.2f}"
            )
        else:
            # Clear title when mouse is outside valid data area
            self.plot_item.setTitle(f"{self.title} Color Map (X-Z Plane)")


class SimplePyQtGraphWidget(QWidget):
    """Simple widget for pyqtgraph visualization with hover info"""

    def __init__(self, title="Base", parent=None):
        super().__init__(parent)
        self.title = title

        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Create GraphicsLayoutWidget
        self.graphics_layout = pg.GraphicsLayoutWidget()
        self.graphics_layout.setBackground("w")
        self.graphics_layout.setMinimumHeight(400)

        # Add histogram for color control on the left side (column 0)
        self.hist_item = pg.HistogramLUTItem(orientation="vertical")
        self.hist_item.setMaximumWidth(150)
        self.graphics_layout.addItem(self.hist_item, row=0, col=0, rowspan=1)

        # Use inferno colormap as requested
        self.hist_item.gradient.loadPreset("inferno")

        # Move to column 1 for the main plot
        self.graphics_layout.nextColumn()

        # Create the main plot
        self.plot_item = self.graphics_layout.addPlot(
            title=f"{title} Color Map (X-Z Plane)"
        )
        self.plot_item.setLabel("bottom", "X Position", units="mm")
        self.plot_item.setLabel("left", "Z Position", units="mm")
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        # Create custom image item with hover functionality
        self.image_item = HoverImageItem(title=title)
        self.image_item.setPlotItem(self.plot_item)
        self.plot_item.addItem(self.image_item)

        # Set inferno colormap
        self.image_item.setColorMap(pg.colormap.get("inferno"))

        # Connect histogram to image item
        self.hist_item.setImageItem(self.image_item)

        # Add to main layout
        main_layout.addWidget(self.graphics_layout, stretch=1)

        self.setLayout(main_layout)

        # Store data for updates
        self.current_data = None

    def update_visualization(self):
        """Update the visualization with current data"""
        if self.current_data is None:
            return

        amplitude = np.array(self.current_data["amplitude"])
        x_data = np.array(self.current_data["x"])
        z_data = np.array(self.current_data["z"])

        self.image_item.setImage(amplitude, autoLevels=False, autoRange=False)

        x_step = x_data[1] - x_data[0] if len(x_data) > 1 else 1
        z_step = z_data[1] - z_data[0] if len(z_data) > 1 else 1

        tr = QtGui.QTransform()
        tr.translate(x_data[0], z_data[0])
        tr.scale(x_step, z_step)
        self.image_item.setTransform(tr)

        # Auto scale color range
        if amplitude.size > 0:
            min_val = np.min(amplitude)
            max_val = np.max(amplitude)
            self.hist_item.setLevels(min_val, max_val)

    def update_data(self, data):
        """Update the data and refresh visualization"""
        self.current_data = data
        self.update_visualization()


class PhasePyQtGraphWidget(QWidget):
    """Widget for phase visualization with same functionality as amplitude widget"""

    def __init__(self, title="Base", parent=None):
        super().__init__(parent)
        self.title = title

        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Create GraphicsLayoutWidget
        self.graphics_layout = pg.GraphicsLayoutWidget()
        self.graphics_layout.setBackground("w")
        self.graphics_layout.setMinimumHeight(400)

        # Add histogram for color control on the left side (column 0)
        self.hist_item = pg.HistogramLUTItem(orientation="vertical")
        self.hist_item.setMaximumWidth(150)
        self.graphics_layout.addItem(self.hist_item, row=0, col=0, rowspan=1)

        # Use a custom gradient for phase data (blue to red)
        self.hist_item.gradient.setColorMap(
            pg.ColorMap([0, 1], [(0, 0, 255), (255, 0, 0)])
        )

        # Move to column 1 for the main plot
        self.graphics_layout.nextColumn()

        # Create the main plot
        self.plot_item = self.graphics_layout.addPlot(
            title=f"{title} Color Map (X-Z Plane)"
        )
        self.plot_item.setLabel("bottom", "X Position", units="mm")
        self.plot_item.setLabel("left", "Z Position", units="mm")
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        # Create custom image item with hover functionality
        self.image_item = HoverImageItem(title=title)
        self.image_item.setPlotItem(self.plot_item)
        self.plot_item.addItem(self.image_item)

        # Set thermal colormap using ColorMap object
        cmap = pg.ColorMap([0, 1], [(0, 0, 255), (255, 0, 0)])  # Blue to red for phase
        self.image_item.setColorMap(cmap)

        # Connect histogram to image item
        self.hist_item.setImageItem(self.image_item)

        # Add to main layout
        main_layout.addWidget(self.graphics_layout, stretch=1)

        self.setLayout(main_layout)

        # Store data for updates
        self.current_data = None

    def update_visualization(self):
        """Update the visualization with current data"""
        if self.current_data is None:
            return

        phase = np.array(self.current_data["phase"])
        x_data = np.array(self.current_data["x"])
        z_data = np.array(self.current_data["z"])

        self.image_item.setImage(phase, autoLevels=False, autoRange=False)

        x_step = x_data[1] - x_data[0] if len(x_data) > 1 else 1
        z_step = z_data[1] - z_data[0] if len(z_data) > 1 else 1

        tr = QtGui.QTransform()
        tr.translate(x_data[0], z_data[0])
        tr.scale(x_step, z_step)
        self.image_item.setTransform(tr)

        # Auto scale color range
        if phase.size > 0:
            min_val = np.min(phase)
            max_val = np.max(phase)
            self.hist_item.setLevels(min_val, max_val)

    def update_data(self, data):
        """Update the data and refresh visualization"""
        self.current_data = data
        self.update_visualization()


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
        self.amplitude_widget = SimplePyQtGraphWidget(title="Amplitude")

        # Create phase pyqtgraph widget
        self.phase_widget = PhasePyQtGraphWidget(title="Phase")

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
        event.accept()
