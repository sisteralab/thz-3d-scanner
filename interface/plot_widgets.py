import numpy as np
import pyqtgraph as pg
from PySide6 import QtGui
from PySide6.QtCore import QObject, QLoggingCategory, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
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


def extract_xz_slice(data, y_index):
    """Return 2D x-z slice from either 2D or 3D data payload."""
    if not isinstance(data, dict):
        return {}

    amplitude = np.asarray(data.get("amplitude", []))
    if amplitude.ndim != 3:
        return data

    y_len = amplitude.shape[0]
    if y_len == 0:
        return data
    y_idx = int(np.clip(y_index, 0, y_len - 1))

    sliced = dict(data)
    for key in ("amplitude", "phase", "complex_real", "complex_imag"):
        arr = np.asarray(data.get(key, []))
        if arr.ndim == 3 and arr.shape[0] == y_len:
            sliced[key] = arr[y_idx]

    y_axis = np.asarray(data.get("y", np.arange(y_len)), dtype=float)
    if y_axis.size != y_len:
        y_axis = np.arange(y_len, dtype=float)

    sliced["y_index"] = y_idx
    sliced["y_value"] = float(y_axis[y_idx])
    return sliced


class ComplexReferenceController(QObject):
    """Stores selected reference points and emits corrected amplitude/phase maps."""

    corrected_data_ready = Signal(dict)
    selection_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw_data = None
        self.selected_points = []  # [(x_idx, z_idx), ...]
        self.selected_point_set = set()
        self.selected_points_array = np.empty((0, 2), dtype=int)
        self.collection_enabled = True
        self.max_scatter_points = 1200
        self.max_ui_points = 30
        self.preview_ui_points = 4
        self.points_version = 0

    def _sync_points_array(self):
        if self.selected_points:
            self.selected_points_array = np.asarray(self.selected_points, dtype=int)
        else:
            self.selected_points_array = np.empty((0, 2), dtype=int)

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
        point_key = (x_idx, z_idx)

        if point_key in self.selected_point_set:
            return

        self.selected_points.append(point_key)
        self.selected_point_set.add(point_key)
        self._sync_points_array()
        self.points_version += 1
        self._emit_updates()

    def remove_last_point(self):
        if not self.selected_points:
            return
        removed_point = self.selected_points.pop()
        self.selected_point_set.discard(removed_point)
        self._sync_points_array()
        self.points_version += 1
        self._emit_updates()

    def clear_points(self):
        if not self.selected_points:
            return
        self.selected_points = []
        self.selected_point_set = set()
        self._sync_points_array()
        self.points_version += 1
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

    @staticmethod
    def _strip_heavy_fields(data):
        if not isinstance(data, dict):
            return {}
        # Keep full metadata for UI, but never pass heavy raw traces through live update signal.
        return {key: value for key, value in data.items() if key != "vna_data"}

    def _build_empty_info(self):
        return {
            "points_preview": [],
            "points_ui": [],
            "scatter_x": np.array([], dtype=float),
            "scatter_z": np.array([], dtype=float),
            "count": 0,
            "points_version": self.points_version,
            "render_key": None,
            "reference_real": None,
            "reference_imag": None,
            "reference_amplitude_db": None,
            "reference_phase_rad": None,
            "points_ui_truncated": False,
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
        if self.selected_points_array.size == 0:
            return self._strip_heavy_fields(data), self._build_empty_info()

        real_map = np.asarray(data.get("complex_real", []), dtype=np.float32)
        imag_map = np.asarray(data.get("complex_imag", []), dtype=np.float32)

        if real_map.ndim != 2 or imag_map.shape != real_map.shape:
            amplitude = np.asarray(data.get("amplitude", []), dtype=np.float32)
            phase = np.asarray(data.get("phase", []), dtype=np.float32)
            if amplitude.ndim != 2 or phase.shape != amplitude.shape:
                return self._strip_heavy_fields(data), self._build_empty_info()

            # Backward-compatible fallback for old datasets without complex maps.
            amp_linear = np.exp(amplitude * np.float32(np.log(10.0) / 20.0))
            real_map = amp_linear * np.cos(phase)
            imag_map = amp_linear * np.sin(phase)

        rows, cols = real_map.shape
        x_axis = np.asarray(data.get("x", np.arange(rows)), dtype=float)
        z_axis = np.asarray(data.get("z", np.arange(cols)), dtype=float)
        if x_axis.size != rows:
            x_axis = np.arange(rows, dtype=float)
        if z_axis.size != cols:
            z_axis = np.arange(cols, dtype=float)

        valid_mask = (
            (self.selected_points_array[:, 0] >= 0)
            & (self.selected_points_array[:, 0] < rows)
            & (self.selected_points_array[:, 1] >= 0)
            & (self.selected_points_array[:, 1] < cols)
        )
        valid_points = self.selected_points_array[valid_mask]
        if valid_points.size == 0:
            return self._strip_heavy_fields(data), self._build_empty_info()

        selected_real = real_map[valid_points[:, 0], valid_points[:, 1]]
        selected_imag = imag_map[valid_points[:, 0], valid_points[:, 1]]
        reference_real = float(np.mean(selected_real, dtype=np.float64))
        reference_imag = float(np.mean(selected_imag, dtype=np.float64))

        corrected_real = real_map - reference_real
        corrected_imag = imag_map - reference_imag
        corrected_amplitude = 20 * np.log10(
            np.clip(np.hypot(corrected_real, corrected_imag), 1e-12, None)
        )
        corrected_phase = np.arctan2(corrected_imag, corrected_real)
        corrected_data = self._strip_heavy_fields(data)
        corrected_data["amplitude"] = corrected_amplitude
        corrected_data["phase"] = corrected_phase
        corrected_data["complex_real"] = corrected_real
        corrected_data["complex_imag"] = corrected_imag

        preview_count = min(self.preview_ui_points, valid_points.shape[0])
        ui_count = min(self.max_ui_points, valid_points.shape[0])
        preview_points = valid_points[:preview_count]
        ui_points = valid_points[:ui_count]
        preview_real = selected_real[:preview_count]
        preview_imag = selected_imag[:preview_count]
        ui_real = selected_real[:ui_count]
        ui_imag = selected_imag[:ui_count]

        scatter_points = valid_points
        if valid_points.shape[0] > self.max_scatter_points:
            stride = int(np.ceil(valid_points.shape[0] / self.max_scatter_points))
            scatter_points = valid_points[::stride]

        points_preview = []
        for point, real_value, imag_value in zip(
            preview_points, preview_real, preview_imag
        ):
            points_preview.append(
                {
                    "x": float(x_axis[point[0]]),
                    "z": float(z_axis[point[1]]),
                    "real": float(real_value),
                    "imag": float(imag_value),
                }
            )

        points_ui = []
        for point, real_value, imag_value in zip(ui_points, ui_real, ui_imag):
            points_ui.append(
                {
                    "x": float(x_axis[point[0]]),
                    "z": float(z_axis[point[1]]),
                    "real": float(real_value),
                    "imag": float(imag_value),
                }
            )

        render_key = (
            self.points_version,
            int(x_axis.size),
            int(z_axis.size),
            float(x_axis[0]),
            float(x_axis[-1]),
            float(z_axis[0]),
            float(z_axis[-1]),
        )

        info = {
            "points_preview": points_preview,
            "points_ui": points_ui,
            "points_ui_truncated": valid_points.shape[0] > ui_count,
            "count": int(valid_points.shape[0]),
            "points_version": self.points_version,
            "render_key": render_key,
            "scatter_x": x_axis[scatter_points[:, 0]],
            "scatter_z": z_axis[scatter_points[:, 1]],
            "reference_real": reference_real,
            "reference_imag": reference_imag,
            "reference_amplitude_db": float(
                20 * np.log10(np.clip(np.hypot(reference_real, reference_imag), 1e-12, None))
            ),
            "reference_phase_rad": float(np.arctan2(reference_imag, reference_real)),
        }

        return corrected_data, info


class ComplexReferenceWidget(QWidget):
    """Small control panel for reference point selection."""

    def __init__(self, controller: ComplexReferenceController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._last_render_key = None

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
        count = int(info.get("count", 0))
        if count:
            self.summary_label.setText(
                "Ref(mean): "
                f"{info['reference_real']:.4e}{info['reference_imag']:+.4e}j "
                f"| {info['reference_amplitude_db']:.2f} dB | "
                f"{info['reference_phase_rad']:.3f} rad"
            )
        else:
            self.summary_label.setText("Ref: none")

        render_key = info.get("render_key")
        if render_key == self._last_render_key:
            return
        self._last_render_key = render_key

        preview_points = info.get("points_preview", [])
        if preview_points:
            preview = []
            for point in preview_points:
                preview.append(f"({point['x']:.2f},{point['z']:.2f})")
            tail = f" +{count - len(preview_points)}" if count > len(preview_points) else ""
            self.points_label.setText(f"P[{count}]: " + ", ".join(preview) + tail)
        else:
            self.points_label.setText("P[0]: none")

        ui_points = info.get("points_ui", [])
        if not ui_points:
            self.points_label.setToolTip("")
            return

        tooltip_lines = []
        for idx, point in enumerate(ui_points, start=1):
            tooltip_lines.append(
                f"{idx}) X={point['x']:.3f}, Z={point['z']:.3f}, "
                f"C={point['real']:.4e}{point['imag']:+.4e}j"
            )
        if info.get("points_ui_truncated", False):
            tooltip_lines.append("... truncated ...")
        self.points_label.setToolTip("\n".join(tooltip_lines))


class YSliceSelectorWidget(QWidget):
    """Y-slice selector with numeric input and slider."""

    y_index_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._y_values = np.array([0.0], dtype=float)
        self._updating = False
        self._current_index = 0

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.title_label = QLabel("Y slice:")
        self.value_spin = QDoubleSpinBox()
        self.value_spin.setDecimals(4)
        self.value_spin.setKeyboardTracking(False)
        self.value_spin.setSingleStep(0.1)
        self.value_spin.setMinimumWidth(120)
        self.value_spin.setSuffix(" mm")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.index_label = QLabel("0/0")
        self.index_label.setMinimumWidth(50)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_spin)
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.index_label)
        self.setLayout(layout)

        self.value_spin.valueChanged.connect(self._on_spin_changed)
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.setVisible(False)

    def set_y_values(self, y_values):
        values = np.asarray(y_values, dtype=float)
        if values.size == 0:
            values = np.array([0.0], dtype=float)
        self._y_values = values
        self.slider.setMaximum(max(values.size - 1, 0))
        self.setVisible(values.size > 1)
        self.set_index(min(self._current_index, values.size - 1), emit_signal=False)

    def set_index(self, index, emit_signal=True):
        if self._y_values.size == 0:
            return

        idx = int(np.clip(index, 0, self._y_values.size - 1))
        if idx == self._current_index and emit_signal:
            self.y_index_changed.emit(idx)
            return

        self._updating = True
        self._current_index = idx
        self.slider.setValue(idx)
        self.value_spin.setRange(float(np.min(self._y_values)), float(np.max(self._y_values)))
        self.value_spin.setValue(float(self._y_values[idx]))
        self.index_label.setText(f"{idx + 1}/{self._y_values.size}")
        self._updating = False

        if emit_signal:
            self.y_index_changed.emit(idx)

    def _on_slider_changed(self, index):
        if self._updating:
            return
        self.set_index(index, emit_signal=True)

    def _on_spin_changed(self, value):
        if self._updating or self._y_values.size == 0:
            return
        idx = int(np.argmin(np.abs(self._y_values - float(value))))
        self.set_index(idx, emit_signal=True)


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
        self._last_markers_render_key = None

        self.roi.sigRegionChanged.connect(self.update_roi_plot)
        self.plot_item.scene().sigMouseMoved.connect(self.mouse_moved)
        self.plot_item.scene().sigMouseClicked.connect(self.mouse_clicked)

        if self.reference_controller is not None:
            self.reference_controller.selection_changed.connect(
                self.update_reference_points
            )

    @staticmethod
    def _axis_edges(axis):
        axis = np.asarray(axis, dtype=float)
        if axis.size == 0:
            return np.array([], dtype=float)
        if axis.size == 1:
            center = float(axis[0])
            return np.array([center - 0.5, center + 0.5], dtype=float)

        edges = np.empty(axis.size + 1, dtype=float)
        edges[1:-1] = 0.5 * (axis[:-1] + axis[1:])
        edges[0] = axis[0] - 0.5 * (axis[1] - axis[0])
        edges[-1] = axis[-1] + 0.5 * (axis[-1] - axis[-2])
        return edges

    @staticmethod
    def _axis_cell_bounds(axis):
        edges = BasePlotWidget._axis_edges(axis)
        if edges.size < 2:
            return np.array([], dtype=float), np.array([], dtype=float)
        low = np.minimum(edges[:-1], edges[1:])
        high = np.maximum(edges[:-1], edges[1:])
        return low, high

    @staticmethod
    def _roi_bounds(roi):
        pos = roi.pos()
        size = roi.size()
        x0 = float(pos.x())
        x1 = float(pos.x() + size.x())
        z0 = float(pos.y())
        z1 = float(pos.y() + size.y())
        return min(x0, x1), max(x0, x1), min(z0, z1), max(z0, z1)

    @staticmethod
    def _in_axis_bounds(axis, value):
        low, high = BasePlotWidget._axis_cell_bounds(axis)
        if low.size == 0:
            return False
        lower = float(np.min(low))
        upper = float(np.max(high))
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
        render_key = info.get("render_key")
        if render_key == self._last_markers_render_key:
            return
        self._last_markers_render_key = render_key

        scatter_x = np.asarray(info.get("scatter_x", []), dtype=float)
        scatter_z = np.asarray(info.get("scatter_z", []), dtype=float)
        if scatter_x.size == 0 or scatter_z.size == 0:
            self.reference_points_scatter.clear()
            return

        self.reference_points_scatter.setData(x=scatter_x, y=scatter_z)

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

        x_edges = self._axis_edges(x_data)
        z_edges = self._axis_edges(z_data)
        if x_edges.size >= 2:
            x_start = float(x_edges[0])
            x_step = float((x_edges[-1] - x_edges[0]) / max(1, x_data.size))
        else:
            x_start = float(x_data[0]) if x_data.size else 0.0
            x_step = 1.0
        if z_edges.size >= 2:
            z_start = float(z_edges[0])
            z_step = float((z_edges[-1] - z_edges[0]) / max(1, z_data.size))
        else:
            z_start = float(z_data[0]) if z_data.size else 0.0
            z_step = 1.0

        transform = QtGui.QTransform()
        # Place image cells so axis values match pixel centers.
        transform.translate(x_start, z_start)
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
            x_low, x_high = self._axis_cell_bounds(self.x_axis)
            z_low, z_high = self._axis_cell_bounds(self.z_axis)
            if (
                x_low.size != data.shape[0]
                or x_high.size != data.shape[0]
                or z_low.size != data.shape[1]
                or z_high.size != data.shape[1]
            ):
                return

            roi_x_min, roi_x_max, roi_z_min, roi_z_max = self._roi_bounds(self.roi)
            x_indices = np.where((x_high >= roi_x_min) & (x_low <= roi_x_max))[0]
            z_indices = np.where((z_high >= roi_z_min) & (z_low <= roi_z_max))[0]
            if x_indices.size == 0 or z_indices.size == 0:
                if self.roi_data_curve is not None:
                    self.roi_data_curve.clear()
                return

            roi_data = data[np.ix_(x_indices, z_indices)]
            mean_data = np.mean(roi_data, axis=1)
            x_positions = self.x_axis[x_indices]

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
        self._source_data = None
        self._current_y_index = 0

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        controls_layout = QHBoxLayout()
        self.drop_raw_checkbox = QCheckBox("Drop raw traces (vna_data) in viewer")
        self.drop_raw_checkbox.setChecked(True)
        self.drop_raw_checkbox.setToolTip(
            "When enabled, raw VNA traces are not held in this window to reduce RAM usage."
        )
        controls_layout.addWidget(self.drop_raw_checkbox)
        controls_layout.addStretch(1)
        main_layout.addLayout(controls_layout)

        self.y_slice_widget = YSliceSelectorWidget()
        self.y_slice_widget.y_index_changed.connect(self._on_y_slice_changed)
        main_layout.addWidget(self.y_slice_widget)

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
        self.drop_raw_checkbox.toggled.connect(self._on_drop_raw_toggled)
        self.update_data(data)

    def _apply_corrected_data(self, data):
        self.amplitude_widget.update_data(data)
        self.phase_widget.update_data(data)

    def _prepare_view_data(self, data):
        if (
            self.drop_raw_checkbox.isChecked()
            and isinstance(data, dict)
            and "vna_data" in data
        ):
            return {key: value for key, value in data.items() if key != "vna_data"}
        return data

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

    def _on_drop_raw_toggled(self, _checked):
        if self._source_data is None:
            return
        self._push_current_slice()

    def _on_y_slice_changed(self, y_index):
        self._current_y_index = int(y_index)
        self._push_current_slice()

    def _push_current_slice(self):
        if self._source_data is None:
            return
        view_data = self._prepare_view_data(self._source_data)
        slice_data = extract_xz_slice(view_data, self._current_y_index)
        self.reference_controller.set_raw_data(slice_data)

    def update_data(self, data):
        self._source_data = data
        y_axis = self._extract_y_axis(data)
        self.y_slice_widget.set_y_values(y_axis)
        self._current_y_index = int(np.clip(self._current_y_index, 0, y_axis.size - 1))
        self.y_slice_widget.set_index(self._current_y_index, emit_signal=False)
        self._push_current_slice()


def build_demo_data(nx=220, nz=140, ny=9):
    """Generate synthetic amplitude/phase data for standalone widget testing."""
    x = np.linspace(-25.0, 25.0, nx)
    y = np.linspace(-4.0, 4.0, ny)
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

    complex_volume = np.empty((ny, nx, nz), dtype=np.complex64)
    for y_idx, y_val in enumerate(y):
        phase_shift = np.exp(1j * (0.25 * y_val))
        amp_scale = 1.0 + 0.05 * np.cos(0.8 * y_val)
        complex_volume[y_idx] = (complex_map * amp_scale * phase_shift).astype(
            np.complex64
        )

    amplitude, phase = complex_to_amplitude_phase(complex_volume)
    return {
        "freq_1": 142.35000,
        "freq_2": 142.35000,
        "amp_1": -20.0,
        "x": x,
        "y": y,
        "z": z,
        "complex_real": np.real(complex_volume),
        "complex_imag": np.imag(complex_volume),
        "amplitude": amplitude,
        "phase": phase,
    }


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    QLoggingCategory.setFilterRules("qt.pointer.dispatch=false")
    app = QApplication.instance() or QApplication([])
    demo_window = DataVisualizationWindow(build_demo_data(), comment="Demo")
    demo_window.show()
    app.exec()
