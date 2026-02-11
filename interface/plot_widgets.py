import numpy as np
import pyqtgraph as pg
from PySide6 import QtGui
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout


def normalize_phase(phase_data):
    """
    Normalize phase data to [-π, π] range, accounting for periodicity.

    Args:
        phase_data: Input phase data (can be single value or array)

    Returns:
        Normalized phase data in range [-π, π]
    """
    phase_array = np.array(phase_data)
    # Convert to numpy array if not already
    if phase_array.ndim == 0:
        # Single value
        phase_array = np.array([phase_array])

    # Normalize to [0, 2π] first
    normalized = phase_array % (2 * np.pi)

    # Convert to [-π, π] range
    normalized[normalized > np.pi] -= 2 * np.pi

    return normalized if phase_array.ndim > 0 else normalized[0]


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
        if 0 <= x < self.image.shape[1] and 0 <= y < self.image.shape[0]:
            value = self.image[y, x]

            # Get real world coordinates
            scene_pos = self.mapToParent(pos)
            x_world = scene_pos.x()
            y_world = scene_pos.y()

            # Update plot title with hover information (similar to example format)
            self.plot_item.setTitle(
                f"{self.title}: {value:.2f}, X: {x_world:.1f} mm, Z: {y_world:.1f} mm"
            )
        else:
            # Clear title when mouse is outside valid data area
            self.plot_item.setTitle(f"{self.title} Color Map (X-Z Plane)")


class BasePlotWidget(QWidget):
    """Base widget for pyqtgraph visualization with hover info"""

    def __init__(
        self, parent=None, title="", data_key="amplitude", colormap_name="inferno"
    ):
        super().__init__(parent)

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

        # Set specified colormap
        if colormap_name == "phase":
            # Custom blue-to-red colormap for phase
            cmap = pg.ColorMap([0, 1], [(0, 0, 255), (255, 0, 0)])
            self.image_item.setColorMap(cmap)
            self.hist_item.gradient.setColorMap(cmap)
        else:
            # Use inferno colormap for amplitude
            self.hist_item.gradient.loadPreset(colormap_name)
            self.image_item.setColorMap(pg.colormap.get(colormap_name))

        # Connect histogram to image item
        self.hist_item.setImageItem(self.image_item)

        # Add to main layout
        main_layout.addWidget(self.graphics_layout, stretch=1)

        self.setLayout(main_layout)

        # Store data for updates
        self.current_data = None
        self.data_key = data_key

    def update_visualization(self):
        """Update the visualization with current data"""
        if self.current_data is None:
            return

        data = np.array(self.current_data[self.data_key])
        x_data = np.array(self.current_data["x"])
        z_data = np.array(self.current_data["z"])

        # Normalize phase data if this is a phase widget
        if self.data_key == "phase":
            data = normalize_phase(data)

        self.image_item.setImage(data)

        x_step = x_data[1] - x_data[0] if len(x_data) > 1 else 1
        z_step = z_data[1] - z_data[0] if len(z_data) > 1 else 1

        tr = QtGui.QTransform()
        tr.translate(x_data[0], z_data[0])
        tr.scale(x_step, z_step)
        self.image_item.setTransform(tr)

        # Auto scale color range
        if data.size > 0:
            min_val = np.min(data)
            max_val = np.max(data)
            self.hist_item.setLevels(min_val, max_val)

    def update_data(self, data):
        """Update the data and refresh visualization"""
        self.current_data = data
        self.update_visualization()


class AmplitudePlotWidget(BasePlotWidget):
    """Widget for amplitude visualization"""

    def __init__(self, parent=None):
        super().__init__(
            parent, title="Amplitude", data_key="amplitude", colormap_name="inferno"
        )


class PhasePlotWidget(BasePlotWidget):
    """Widget for phase visualization"""

    def __init__(self, parent=None):
        super().__init__(parent, title="Phase", data_key="phase", colormap_name="phase")


class DataVisualizationWindow(QWidget):
    """Window for visualizing amplitude and phase data"""

    def __init__(self, data, comment="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            f"{comment} - Freq1: {data.get('freq_1', 'N/A'):.5f} GHz, Freq2: {data.get('freq_2', 'N/A'):.5f} GHz"
        )
        self.resize(1000, 600)

        # Create main layout
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)

        # Create amplitude widget
        self.amplitude_widget = AmplitudePlotWidget()

        # Create phase widget
        self.phase_widget = PhasePlotWidget()

        # Add widgets to layout
        main_layout.addWidget(self.amplitude_widget, stretch=1)
        main_layout.addWidget(self.phase_widget, stretch=1)

        self.setLayout(main_layout)

        # Update with data
        self.update_data(data)

    def update_data(self, data):
        """Update both widgets with data"""
        self.amplitude_widget.update_data(data)
        self.phase_widget.update_data(data)
