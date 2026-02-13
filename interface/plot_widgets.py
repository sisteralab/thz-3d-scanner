import numpy as np
import pyqtgraph as pg
from PySide6 import QtGui
from PySide6.QtCore import QObject, QLoggingCategory, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def normalize_phase(phase_data):
    """Normalize phase to [-pi, pi]."""
    phase_array = np.asarray(phase_data, dtype=float)
    return (phase_array + np.pi) % (2 * np.pi) - np.pi


def amplitude_phase_to_complex(amplitude_db, phase_rad):
    amplitude_linear = np.power(10.0, np.asarray(amplitude_db, dtype=float) / 20.0)
    phase = np.asarray(phase_rad, dtype=float)
    return amplitude_linear * np.exp(1j * phase)


def complex_to_amplitude_phase(complex_data):
    magnitude = np.abs(complex_data)
    amplitude_db = 20 * np.log10(np.clip(magnitude, 1e-12, None))
    phase = normalize_phase(np.angle(complex_data))
    return amplitude_db, phase


class ComplexReferenceController(QObject):
    """Stores selected reference points and emits corrected amplitude/phase maps."""

    corrected_data_ready = Signal(dict)
    selection_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw_data = None
        self.selected_points = []  # [(x_coord, z_coord), ...]
        self.collection_enabled = True

    def set_raw_data(self, data):
        self.raw_data = data
        self._emit_updates()

    def add_point(self, x_coord, z_coord):
        if self.raw_data is None or not self.collection_enabled:
            return

        x_axis, z_axis = self._get_axes(self.raw_data)
        if x_axis.size == 0 or z_axis.size == 0:
            return

        x_idx = int(np.argmin(np.abs(x_axis - x_coord)))
        z_idx = int(np.argmin(np.abs(z_axis - z_coord)))
        snapped_x = float(x_axis[x_idx])
        snapped_z = float(z_axis[z_idx])

        for px, pz in self.selected_points:
            if np.isclose(px, snapped_x) and np.isclose(pz, snapped_z):
                return

        self.selected_points.append((snapped_x, snapped_z))
        self._emit_updates()

    def remove_last_point(self):
        if not self.selected_points:
            return
        self.selected_points.pop()
        self._emit_updates()

    def clear_points(self):
        self.selected_points = []
        self._emit_updates()

    def set_collection_enabled(self, enabled):
        self.collection_enabled = bool(enabled)

    def _emit_updates(self):
        if self.raw_data is None:
            self.selection_changed.emit(self._build_empty_info())
            return

        corrected_data, info = self._build_corrected_data(self.raw_data)
        self.selection_changed.emit(info)
        self.corrected_data_ready.emit(corrected_data)

    def _build_empty_info(self):
        return {
            "points": [],
            "count": 0,
            "reference_real": None,
            "reference_imag": None,
            "reference_amplitude_db": None,
            "reference_phase_rad": None,
        }

    @staticmethod
    def _get_axes(data):
        amplitude = np.asarray(data.get("amplitude", []), dtype=float)
        if amplitude.ndim != 2:
            return np.array([]), np.array([])

        x_axis = np.asarray(data.get("x", np.arange(amplitude.shape[0])), dtype=float)
        z_axis = np.asarray(data.get("z", np.arange(amplitude.shape[1])), dtype=float)

        if x_axis.size != amplitude.shape[0]:
            x_axis = np.arange(amplitude.shape[0], dtype=float)
        if z_axis.size != amplitude.shape[1]:
            z_axis = np.arange(amplitude.shape[1], dtype=float)

        return x_axis, z_axis

    def _build_corrected_data(self, data):
        amplitude = np.asarray(data.get("amplitude", []), dtype=float)
        phase = np.asarray(data.get("phase", []), dtype=float)
        if amplitude.ndim != 2 or phase.shape != amplitude.shape:
            return data, self._build_empty_info()

        x_axis, z_axis = self._get_axes(data)
        if x_axis.size == 0 or z_axis.size == 0:
            return data, self._build_empty_info()

        complex_map = amplitude_phase_to_complex(amplitude, phase)
        point_infos = []
        point_complex_values = []

        for point_x, point_z in self.selected_points:
            x_idx = int(np.argmin(np.abs(x_axis - point_x)))
            z_idx = int(np.argmin(np.abs(z_axis - point_z)))
            value = complex_map[x_idx, z_idx]
            point_complex_values.append(value)
            point_infos.append(
                {
                    "x": float(x_axis[x_idx]),
                    "z": float(z_axis[z_idx]),
                    "x_idx": x_idx,
                    "z_idx": z_idx,
                    "real": float(np.real(value)),
                    "imag": float(np.imag(value)),
                    "amplitude_db": float(
                        20 * np.log10(np.clip(np.abs(value), 1e-12, None))
                    ),
                    "phase_rad": float(normalize_phase(np.angle(value))),
                }
            )

        if point_complex_values:
            reference_complex = np.mean(np.asarray(point_complex_values, dtype=complex))
            corrected_complex = complex_map - reference_complex
            info = {
                "points": point_infos,
                "count": len(point_infos),
                "reference_real": float(np.real(reference_complex)),
                "reference_imag": float(np.imag(reference_complex)),
                "reference_amplitude_db": float(
                    20 * np.log10(np.clip(np.abs(reference_complex), 1e-12, None))
                ),
                "reference_phase_rad": float(normalize_phase(np.angle(reference_complex))),
            }
        else:
            corrected_complex = complex_map.copy()
            info = self._build_empty_info()

        corrected_amplitude, corrected_phase = complex_to_amplitude_phase(
            corrected_complex
        )
        corrected_data = dict(data)
        corrected_data["amplitude"] = corrected_amplitude
        corrected_data["phase"] = corrected_phase

        return corrected_data, info


class ComplexReferenceWidget(QWidget):
    """Small control panel for reference point selection."""

    def __init__(self, controller: ComplexReferenceController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        self.enable_collect_checkbox = QCheckBox("Collect points")
        self.enable_collect_checkbox.setChecked(self.controller.collection_enabled)
        self.hint_label = QLabel("Click Amplitude map (X horizontal, Z vertical)")
        self.hint_label.setStyleSheet("color: #666;")

        self.remove_last_button = QPushButton("Undo")
        self.clear_button = QPushButton("Clear")
        self.remove_last_button.setMaximumWidth(70)
        self.clear_button.setMaximumWidth(70)
        self.remove_last_button.setMaximumHeight(24)
        self.clear_button.setMaximumHeight(24)

        top_row.addWidget(self.enable_collect_checkbox)
        top_row.addWidget(self.hint_label, stretch=1)
        top_row.addWidget(self.remove_last_button)
        top_row.addWidget(self.clear_button)

        self.summary_label = QLabel("Ref: none")
        self.points_label = QLabel("P[0]: none")
        self.points_label.setStyleSheet("color: #555;")
        self.points_label.setWordWrap(False)

        layout.addLayout(top_row)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.points_label)
        self.setLayout(layout)
        self.setMaximumHeight(88)

        self.remove_last_button.clicked.connect(self.controller.remove_last_point)
        self.clear_button.clicked.connect(self.controller.clear_points)
        self.enable_collect_checkbox.toggled.connect(
            self.controller.set_collection_enabled
        )
        self.controller.selection_changed.connect(self.update_from_selection)

    def update_from_selection(self, info):
        points = info.get("points", [])
        if points:
            preview = []
            for point in points[:4]:
                preview.append(f"({point['x']:.2f},{point['z']:.2f})")
            tail = f" +{len(points) - 4}" if len(points) > 4 else ""
            self.points_label.setText(
                f"P[{len(points)}]: " + ", ".join(preview) + tail
            )

            tooltip_lines = []
            for idx, point in enumerate(points, start=1):
                tooltip_lines.append(
                    f"{idx}) X={point['x']:.3f}, Z={point['z']:.3f}, "
                    f"C={point['real']:.4e}{point['imag']:+.4e}j"
                )
            self.points_label.setToolTip("\n".join(tooltip_lines))
        else:
            self.points_label.setText("P[0]: none")
            self.points_label.setToolTip("")

        if info.get("count", 0):
            self.summary_label.setText(
                "Ref(mean): "
                f"{info['reference_real']:.4e}{info['reference_imag']:+.4e}j "
                f"| {info['reference_amplitude_db']:.2f} dB | "
                f"{info['reference_phase_rad']:.3f} rad"
            )
        else:
            self.summary_label.setText("Ref: none")


class BasePlotWidget(QWidget):
    """Base widget for pyqtgraph visualization with hover info."""

    def __init__(
        self,
        parent=None,
        title="",
        data_key="amplitude",
        colormap_name="inferno",
        reference_controller: ComplexReferenceController = None,
        allow_reference_selection=False,
    ):
        super().__init__(parent)

        self.reference_controller = reference_controller
        self.allow_reference_selection = allow_reference_selection

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        self.graphics_layout = pg.GraphicsLayoutWidget()
        self.graphics_layout.setBackground("w")
        self.graphics_layout.setMinimumHeight(400)

        self.hist_item = pg.HistogramLUTItem(orientation="vertical")
        self.hist_item.setMaximumWidth(150)
        self.graphics_layout.addItem(self.hist_item, row=0, col=0, rowspan=1)
        self.graphics_layout.nextColumn()

        self.plot_item = self.graphics_layout.addPlot(
            title=f"{title} Color Map (X-Z Plane)"
        )
        self.plot_item.setLabel("bottom", "X Position", units="mm")
        self.plot_item.setLabel("left", "Z Position", units="mm")
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)

        self.image_item = pg.ImageItem(axisOrder="col-major")
        self.plot_item.addItem(self.image_item)

        if colormap_name == "phase":
            cmap = pg.ColorMap([0, 1], [(0, 0, 255), (255, 0, 0)])
            self.image_item.setColorMap(cmap)
            self.hist_item.gradient.setColorMap(cmap)
        else:
            self.hist_item.gradient.loadPreset(colormap_name)
            self.image_item.setColorMap(pg.colormap.get(colormap_name))

        self.hist_item.setImageItem(self.image_item)

        self.reference_points_scatter = pg.ScatterPlotItem(
            size=11,
            pen=pg.mkPen((0, 255, 255), width=2),
            brush=pg.mkBrush(0, 0, 0, 0),
            symbol="x",
        )
        self.plot_item.addItem(self.reference_points_scatter)

        self.roi = pg.ROI([0, 0], [10, 2], pen=(0, 9))
        self.roi.addScaleHandle([0.5, 1], [0.5, 0.5])
        self.roi.addScaleHandle([0, 0.5], [0.5, 0.5])
        self.plot_item.addItem(self.roi)
        self.roi.setZValue(10)

        self.roi_plot_item = pg.plot(title="ROI Data", colspan=2)
        self.roi_plot_item.setBackground("w")
        self.roi_plot_item.setMinimumHeight(150)
        self.roi_plot_item.setMaximumHeight(250)
        self.roi_plot_item.setLabel("bottom", "Position", units="mm")
        self.roi_plot_item.setLabel("left", "Value")
        self.roi_plot_item.showGrid(x=True, y=True, alpha=0.3)

        main_layout.addWidget(self.graphics_layout, stretch=1)
        main_layout.addWidget(self.roi_plot_item, stretch=1)
        self.setLayout(main_layout)

        self.current_data = None
        self.data_key = data_key
        self.title = title
        self.roi_data_curve = None
        self.display_data = None
        self.x_axis = np.array([])
        self.z_axis = np.array([])

        self.roi.sigRegionChanged.connect(self.update_roi_plot)
        self.plot_item.scene().sigMouseMoved.connect(self.mouse_moved)
        self.plot_item.scene().sigMouseClicked.connect(self.mouse_clicked)

        if self.reference_controller is not None:
            self.reference_controller.selection_changed.connect(
                self.update_reference_points
            )

    @staticmethod
    def _in_axis_bounds(axis, value):
        if axis.size == 0:
            return False
        if axis.size == 1:
            return np.isclose(value, axis[0], atol=1.0)
        step = float(np.min(np.abs(np.diff(axis))))
        if step == 0:
            step = 1.0
        lower = float(np.min(axis) - step / 2)
        upper = float(np.max(axis) + step / 2)
        return lower <= value <= upper

    def _map_world_to_indices(self, x_world, z_world):
        if (
            self.display_data is None
            or self.display_data.ndim != 2
            or self.x_axis.size == 0
            or self.z_axis.size == 0
        ):
            return None

        if not self._in_axis_bounds(self.x_axis, x_world) or not self._in_axis_bounds(
            self.z_axis, z_world
        ):
            return None

        x_idx = int(np.argmin(np.abs(self.x_axis - x_world)))
        z_idx = int(np.argmin(np.abs(self.z_axis - z_world)))
        if (
            0 <= x_idx < self.display_data.shape[0]
            and 0 <= z_idx < self.display_data.shape[1]
        ):
            return x_idx, z_idx
        return None

    def _reset_title(self):
        self.plot_item.setTitle(f"{self.title} Color Map (X-Z Plane)")

    def mouse_moved(self, scene_pos):
        if not self.plot_item.sceneBoundingRect().contains(scene_pos):
            self._reset_title()
            return

        point = self.plot_item.vb.mapSceneToView(scene_pos)
        indices = self._map_world_to_indices(point.x(), point.y())
        if indices is None:
            self._reset_title()
            return

        x_idx, z_idx = indices
        value = float(self.display_data[x_idx, z_idx])
        x_coord = float(self.x_axis[x_idx])
        z_coord = float(self.z_axis[z_idx])
        self.plot_item.setTitle(
            f"{self.title}: {value:.3f}, X: {x_coord:.3f} mm, Z: {z_coord:.3f} mm"
        )

    def mouse_clicked(self, mouse_event):
        if (
            not self.allow_reference_selection
            or self.reference_controller is None
            or mouse_event.button() != Qt.MouseButton.LeftButton
        ):
            return

        scene_pos = mouse_event.scenePos()
        if not self.plot_item.sceneBoundingRect().contains(scene_pos):
            return

        point = self.plot_item.vb.mapSceneToView(scene_pos)
        indices = self._map_world_to_indices(point.x(), point.y())
        if indices is None:
            return

        x_idx, z_idx = indices
        self.reference_controller.add_point(
            float(self.x_axis[x_idx]),
            float(self.z_axis[z_idx]),
        )
        mouse_event.accept()

    def update_reference_points(self, info):
        points = info.get("points", [])
        if not points:
            self.reference_points_scatter.setData([])
            return

        spots = [{"pos": (point["x"], point["z"])} for point in points]
        self.reference_points_scatter.setData(spots)

    def update_visualization(self):
        if self.current_data is None:
            return

        data = np.asarray(self.current_data.get(self.data_key, []), dtype=float)
        if data.ndim != 2:
            return

        if self.data_key == "phase":
            data = normalize_phase(data)

        self.display_data = data

        x_data = np.asarray(self.current_data.get("x", np.arange(data.shape[0])))
        z_data = np.asarray(self.current_data.get("z", np.arange(data.shape[1])))
        if x_data.size != data.shape[0]:
            x_data = np.arange(data.shape[0], dtype=float)
        else:
            x_data = x_data.astype(float)
        if z_data.size != data.shape[1]:
            z_data = np.arange(data.shape[1], dtype=float)
        else:
            z_data = z_data.astype(float)

        self.x_axis = x_data
        self.z_axis = z_data

        self.image_item.setImage(data, autoLevels=False)

        x_step = x_data[1] - x_data[0] if len(x_data) > 1 else 1
        z_step = z_data[1] - z_data[0] if len(z_data) > 1 else 1

        transform = QtGui.QTransform()
        transform.translate(float(x_data[0]), float(z_data[0]))
        transform.scale(float(x_step), float(z_step))
        self.image_item.setTransform(transform)

        self.update_roi_plot()

    def update_roi_plot(self):
        if self.display_data is None:
            return

        data = np.asarray(self.display_data, dtype=float)
        if data.ndim != 2:
            return

        try:
            roi_data = self.roi.getArrayRegion(data, self.image_item)
            if roi_data is None or roi_data.size == 0:
                return

            if roi_data.ndim > 1:
                mean_data = np.mean(roi_data, axis=1)
            else:
                mean_data = roi_data

            roi_pos = self.roi.pos()
            roi_size = self.roi.size()
            x_start = roi_pos.x()
            x_end = x_start + roi_size.x()
            x_positions = np.linspace(x_start, x_end, mean_data.shape[0])

            if self.roi_data_curve is None:
                self.roi_data_curve = self.roi_plot_item.plot(
                    x_positions, mean_data, pen=pg.mkPen("r", width=2), clear=True
                )
            else:
                self.roi_data_curve.setData(x_positions, mean_data)

            self.roi_plot_item.setTitle(f"{self.title} ROI Cross-Section")
            self.roi_plot_item.setLabel("left", self.title)
        except Exception as err:
            print(f"Error updating ROI plot: {err}")

    def update_data(self, data):
        self.current_data = data
        self.update_visualization()


class AmplitudePlotWidget(BasePlotWidget):
    """Widget for amplitude visualization."""

    def __init__(self, parent=None, reference_controller: ComplexReferenceController = None):
        super().__init__(
            parent,
            title="Amplitude",
            data_key="amplitude",
            colormap_name="inferno",
            reference_controller=reference_controller,
            allow_reference_selection=True,
        )


class PhasePlotWidget(BasePlotWidget):
    """Widget for phase visualization."""

    def __init__(self, parent=None, reference_controller: ComplexReferenceController = None):
        super().__init__(
            parent,
            title="Phase",
            data_key="phase",
            colormap_name="phase",
            reference_controller=reference_controller,
            allow_reference_selection=False,
        )


class DataVisualizationWindow(QWidget):
    """Window for visualizing amplitude and phase data."""

    def __init__(self, data, comment="", parent=None):
        super().__init__(parent)

        freq_1 = data.get("freq_1")
        freq_2 = data.get("freq_2")
        freq_1_text = f"{freq_1:.5f}" if isinstance(freq_1, (int, float, np.floating)) else "N/A"
        freq_2_text = f"{freq_2:.5f}" if isinstance(freq_2, (int, float, np.floating)) else "N/A"

        self.setWindowTitle(
            f"{comment} - Freq1: {freq_1_text} GHz, Freq2: {freq_2_text} GHz"
        )
        self.resize(1200, 760)

        self.reference_controller = ComplexReferenceController(self)
        self.reference_controller.corrected_data_ready.connect(self._apply_corrected_data)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        self.reference_widget = ComplexReferenceWidget(self.reference_controller)
        main_layout.addWidget(self.reference_widget)

        plots_layout = QHBoxLayout()
        plots_layout.setSpacing(10)
        self.amplitude_widget = AmplitudePlotWidget(
            reference_controller=self.reference_controller
        )
        self.phase_widget = PhasePlotWidget(reference_controller=self.reference_controller)
        plots_layout.addWidget(self.amplitude_widget, stretch=1)
        plots_layout.addWidget(self.phase_widget, stretch=1)
        main_layout.addLayout(plots_layout, stretch=1)

        self.setLayout(main_layout)
        self.update_data(data)

    def _apply_corrected_data(self, data):
        self.amplitude_widget.update_data(data)
        self.phase_widget.update_data(data)

    def update_data(self, data):
        self.reference_controller.set_raw_data(data)


def build_demo_data(nx=220, nz=140):
    """Generate synthetic amplitude/phase data for standalone widget testing."""
    x = np.linspace(-25.0, 25.0, nx)
    z = np.linspace(-12.0, 12.0, nz)
    xx, zz = np.meshgrid(x, z, indexing="ij")

    # Build complex field with smooth structures and fixed complex background offset.
    magnitude = (
        0.02
        + 0.45 * np.exp(-((xx - 7.0) ** 2 + (zz + 3.0) ** 2) / 95.0)
        + 0.33 * np.exp(-((xx + 11.0) ** 2 + (zz - 4.0) ** 2) / 120.0)
    )
    phase = 0.17 * xx - 0.19 * zz + 0.75 * np.sin(xx / 6.5) * np.cos(zz / 4.2)
    complex_map = magnitude * np.exp(1j * phase)
    complex_map += 0.03 * np.exp(1j * 1.1)

    amplitude, phase = complex_to_amplitude_phase(complex_map)
    return {
        "freq_1": 142.35000,
        "freq_2": 142.35000,
        "amp_1": -20.0,
        "x": x,
        "y": np.array([0.0]),
        "z": z,
        "amplitude": amplitude,
        "phase": phase,
        "vna_data": [],
    }


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    QLoggingCategory.setFilterRules("qt.pointer.dispatch=false")
    app = QApplication.instance() or QApplication([])
    demo_window = DataVisualizationWindow(build_demo_data(), comment="Demo")
    demo_window.show()
    app.exec()
