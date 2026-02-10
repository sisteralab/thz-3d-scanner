import logging

import numpy as np
import pyqtgraph as pg
from PySide6 import QtGui
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QHBoxLayout,
    QPushButton,
)

from interface.log import LogHandler, LogWidget
from interface.manager_widget import ManagerWidget
from store.state import State


class HoverImageItem(pg.ImageItem):
    """Custom ImageItem with hover functionality to show values"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hover_text = pg.TextItem("", color=(255, 255, 255), anchor=(0.5, 1))
        self.hover_text.setZValue(100)
        self.hover_text.hide()

    def setParentItem(self, parent):
        super().setParentItem(parent)
        if parent is not None:
            parent.scene().sigMouseMoved.connect(self.mouse_moved)
            parent.addItem(self.hover_text)

    def mouse_moved(self, pos):
        if self.image is None:
            return

        # Convert scene position to image coordinates
        pos = self.mapFromScene(pos)
        if not self.boundingRect().contains(pos):
            self.hover_text.hide()
            return

        # Get image coordinates
        img_pos = self.mapFromItem(self, pos)
        x = int(img_pos.x())
        y = int(img_pos.y())

        # Check if coordinates are within image bounds
        if 0 <= x < self.image.shape[1] and 0 <= y < self.image.shape[0]:
            value = self.image[y, x]

            # Show hover text
            self.hover_text.setText(f"X: {x:.1f}, Z: {y:.1f}\nValue: {value:.2f} dB")
            self.hover_text.setPos(pos.x(), pos.y() - 10)
            self.hover_text.show()
        else:
            self.hover_text.hide()


class InteractivePyQtGraphWidget(QWidget):
    """Widget for interactive pyqtgraph visualization with controls"""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        # Create GraphicsLayoutWidget for better layout control
        self.graphics_layout = pg.GraphicsLayoutWidget()
        self.graphics_layout.setBackground("w")
        self.graphics_layout.setMinimumHeight(400)

        # Add histogram for color control on the left side (column 0)
        self.hist_item = pg.HistogramLUTItem(orientation="vertical")
        self.hist_item.setMaximumWidth(150)
        self.graphics_layout.addItem(self.hist_item, row=0, col=0, rowspan=1)

        # Move to column 1 for the main plot
        self.graphics_layout.nextColumn()

        # Create the main plot
        self.plot_item = self.graphics_layout.addPlot(
            title="Amplitude Color Map (X-Z Plane)"
        )
        self.plot_item.setLabel("bottom", "X Position", units="mm")
        self.plot_item.setLabel("left", "Z Position", units="mm")
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        # Create custom image item with hover functionality
        self.image_item = HoverImageItem()
        self.plot_item.addItem(self.image_item)

        # Set default colormap
        self.colormap = pg.colormap.get("viridis")
        self.image_item.setColorMap(self.colormap)

        # Connect histogram to image item
        self.hist_item.setImageItem(self.image_item)
        self.hist_item.gradient.loadPreset("viridis")

        # Create controls layout
        controls_layout = QHBoxLayout()

        # Colormap selection - using only built-in colormaps
        self.colormap_combo = QComboBox()
        self.colormap_combo.addItems(["viridis", "plasma", "inferno", "magma", "turbo"])
        self.colormap_combo.setCurrentText("viridis")
        self.colormap_combo.currentTextChanged.connect(self.change_colormap)

        # Color range controls
        self.min_spin = QDoubleSpinBox()
        self.min_spin.setRange(-100, 100)
        self.min_spin.setValue(-1)
        self.min_spin.setPrefix("Min: ")
        self.min_spin.setSingleStep(0.1)
        self.min_spin.valueChanged.connect(self.update_color_range)

        self.max_spin = QDoubleSpinBox()
        self.max_spin.setRange(-100, 100)
        self.max_spin.setValue(0)
        self.max_spin.setPrefix("Max: ")
        self.max_spin.setSingleStep(0.1)
        self.max_spin.valueChanged.connect(self.update_color_range)

        self.auto_scale_btn = QPushButton("Auto Scale")
        self.auto_scale_btn.clicked.connect(self.auto_scale)

        # Add controls to layout
        controls_layout.addWidget(QLabel("Colormap:"))
        controls_layout.addWidget(self.colormap_combo)
        controls_layout.addStretch()
        controls_layout.addWidget(self.min_spin)
        controls_layout.addWidget(self.max_spin)
        controls_layout.addWidget(self.auto_scale_btn)

        # Create controls widget
        controls_widget = QWidget()
        controls_widget.setLayout(controls_layout)
        controls_widget.setMaximumHeight(50)

        # Add to main layout
        main_layout.addWidget(controls_widget)
        main_layout.addWidget(self.graphics_layout, stretch=1)

        self.setLayout(main_layout)

        # Store data for updates
        self.current_data = None
        self.first_update = True

    def change_colormap(self, colormap_name):
        """Change the colormap"""
        self.colormap = pg.colormap.get(colormap_name)
        self.image_item.setColorMap(self.colormap)
        self.hist_item.gradient.loadPreset(colormap_name)

    def update_color_range(self):
        """Update the color range manually"""
        min_val = self.min_spin.value()
        max_val = self.max_spin.value()
        self.hist_item.setLevels(min_val, max_val)

    def auto_scale(self):
        """Auto scale the color range based on current data"""
        if hasattr(self.image_item, "image") and self.image_item.image is not None:
            data = self.image_item.image
            if data is not None and data.size > 0:
                min_val = np.min(data)
                max_val = np.max(data)

                # Update spin boxes
                self.min_spin.blockSignals(True)
                self.max_spin.blockSignals(True)
                self.min_spin.setValue(min_val)
                self.max_spin.setValue(max_val)
                self.min_spin.blockSignals(False)
                self.max_spin.blockSignals(False)

                # Update color range
                self.update_color_range()

    def update_visualization(self):
        """Update the visualization with current data"""
        if self.current_data is None:
            return

        x_data = np.array(self.current_data["x"])
        z_data = np.array(self.current_data["z"])
        amplitude = np.array(self.current_data["amplitude"])

        # Data comes as [x_points][z_points] from measurement cycle (X first, then Z)
        # For pyqtgraph ImageItem, we need [rows][columns] where rows = y-axis (Z), columns = x-axis (X)
        # So the data is already in correct format: [x_points][z_points] = [columns][rows]
        # No transposition needed!

        # Set image data
        self.image_item.setImage(amplitude)

        # Set up proper transform for axis scaling
        x_step = x_data[1] - x_data[0] if len(x_data) > 1 else 1
        z_step = z_data[1] - z_data[0] if len(z_data) > 1 else 1

        tr = QtGui.QTransform()
        tr.translate(x_data[0] - x_step / 2, z_data[0] - z_step / 2)
        tr.scale(x_step, z_step)
        self.image_item.setTransform(tr)

        # Auto scale color range for first update
        if self.first_update:
            self.auto_scale()
            self.first_update = False

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

        # Create interactive pyqtgraph widget
        self.plot_widget = InteractivePyQtGraphWidget()

        self.log_widget = LogWidget(self)

        left_layout.addWidget(self.plot_widget)
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
                    [-1, 0, 0, -1],
                    [-1, 0, 0, -1],
                    [-1, 0, 0, -1],
                    [-1, 0, 0, -1],
                ],
                "x": [-20, -10, 10, 20],
                "z": [-20, -10, 10, 20],
            }
        )

    def update_plot(self, data):
        """Update the visualization with new measurement data"""
        self.plot_widget.update_data(data)

    def closeEvent(self, event: QtGui.QCloseEvent):
        State.del_scanner()
        State.del_vna()
        State.store_state()
        event.accept()
