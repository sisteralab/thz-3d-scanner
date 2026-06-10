import unittest
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from application.visualization.plot_slicing import (
    PLOT_PLANE_XY,
    PLOT_PLANE_ZX,
    extract_axis_slice,
    plot_slice_axis_name,
)
from interface.plot_widgets import (
    AmplitudePlotWidget,
    BasePlotWidget,
    DataVisualizationWindow,
    PhasePlotWidget,
    build_demo_data,
    phase_rad_to_degrees,
)
from store.state import State


class VisualizationSlicingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_extract_axis_slice_returns_view_and_metadata(self):
        amplitude = np.arange(2 * 3 * 4, dtype=np.float32).reshape(2, 3, 4)
        data = {
            "x": np.arange(3, dtype=np.float32),
            "y": np.arange(2, dtype=np.float32),
            "z": np.arange(4, dtype=np.float32),
            "amplitude": amplitude,
            "phase": amplitude + 1,
            "calibrated_amplitude": amplitude + 2,
        }

        sliced = extract_axis_slice(data, PLOT_PLANE_ZX, 1)

        self.assertEqual(sliced["amplitude"].shape, (3, 4))
        self.assertTrue(np.shares_memory(sliced["amplitude"], amplitude))
        self.assertEqual(sliced["horizontal_axis_name"], "X")
        self.assertEqual(sliced["vertical_axis_name"], "Z")
        self.assertEqual(sliced["slice_axis_name"], "Y")

    def test_plot_slice_axis_tracks_plane(self):
        self.assertEqual(plot_slice_axis_name(PLOT_PLANE_ZX), "Y")
        self.assertEqual(plot_slice_axis_name(PLOT_PLANE_XY), "Z")

    def test_full_resolution_is_default(self):
        State.plot_max_pixels = 0
        data = np.zeros((300, 400), dtype=np.float32)
        x_axis = np.arange(300, dtype=float)
        z_axis = np.arange(400, dtype=float)

        (
            display,
            x_display,
            z_display,
            stride_x,
            stride_z,
        ) = BasePlotWidget._downsample_for_display(data, x_axis, z_axis)

        self.assertIs(display, data)
        self.assertEqual(stride_x, 1)
        self.assertEqual(stride_z, 1)
        self.assertEqual(x_display.size, x_axis.size)
        self.assertEqual(z_display.size, z_axis.size)

    def test_optional_display_cap_is_only_preview_sampling(self):
        State.plot_max_pixels = 10_000
        data = np.zeros((300, 400), dtype=np.float32)
        x_axis = np.arange(300, dtype=float)
        z_axis = np.arange(400, dtype=float)

        display, _, _, stride_x, stride_z = BasePlotWidget._downsample_for_display(
            data,
            x_axis,
            z_axis,
        )

        self.assertLessEqual(display.size, 10_000)
        self.assertGreater(stride_x, 1)
        self.assertGreater(stride_z, 1)

    def test_phase_display_is_degrees(self):
        degrees = phase_rad_to_degrees(np.array([0.0, np.pi], dtype=np.float32))
        self.assertTrue(np.allclose(degrees, [0.0, 180.0], atol=1e-4))

    def test_manual_color_levels_survive_data_update(self):
        widget = AmplitudePlotWidget()
        x_axis = np.arange(4, dtype=np.float32)
        z_axis = np.arange(4, dtype=np.float32)
        first = np.arange(16, dtype=np.float32).reshape(4, 4)
        second = first + np.float32(100.0)
        payload = {
            "x": x_axis,
            "z": z_axis,
            "amplitude": first,
            "has_late_samples": False,
        }

        widget.update_data(payload)
        widget._perform_deferred_updates()
        self.app.processEvents()

        widget.hist_item.setLevels(2.0, 8.0)
        self.app.processEvents()
        self.assertTrue(widget._manual_levels_enabled)

        payload["amplitude"] = second
        widget.update_data(payload)
        widget._perform_deferred_updates()
        self.app.processEvents()

        self.assertEqual(widget._manual_levels, (2.0, 8.0))
        self.assertEqual(tuple(widget.hist_item.getLevels()), (2.0, 8.0))

        widget.reset_auto_levels()
        self.assertFalse(widget._manual_levels_enabled)

    def test_phase_auto_levels_recompute_after_demo_data(self):
        widget = PhasePlotWidget()
        x_axis = np.arange(4, dtype=np.float32)
        z_axis = np.arange(4, dtype=np.float32)
        demo_phase = np.linspace(-5.0, 5.0, 16, dtype=np.float32).reshape(4, 4)
        real_phase = np.linspace(40.0, 80.0, 16, dtype=np.float32).reshape(4, 4)
        payload = {
            "x": x_axis,
            "z": z_axis,
            "phase": demo_phase,
            "phase_degrees": demo_phase,
            "has_late_samples": False,
        }

        widget.update_data(payload)
        widget._perform_deferred_updates()
        self.app.processEvents()
        self.assertEqual(tuple(widget.hist_item.getLevels()), (-5.0, 5.0))

        payload = {
            "x": x_axis,
            "z": z_axis,
            "phase": real_phase,
            "phase_degrees": real_phase,
            "has_late_samples": False,
        }
        widget.update_data(payload)
        widget._perform_deferred_updates()
        self.app.processEvents()

        self.assertEqual(tuple(widget.hist_item.getLevels()), (40.0, 80.0))

    def test_visualization_window_pushes_slice_to_plots(self):
        window = DataVisualizationWindow(build_demo_data(nx=8, nz=7, ny=3))
        self.app.processEvents()
        window.amplitude_widget._perform_deferred_updates()
        window.phase_widget._perform_deferred_updates()

        self.assertIsNotNone(window.amplitude_widget.current_data)
        self.assertIsNotNone(window.phase_widget.current_data)
        self.assertIsNotNone(window.amplitude_widget.display_data)
        self.assertIsNotNone(window.phase_widget.display_data)

    def test_main_window_import_and_initial_plot(self):
        from interface.index import MainWindow

        window = MainWindow()
        self.app.processEvents()
        window._apply_pending_plot_update()
        window.amplitude_widget._perform_deferred_updates()
        window.phase_widget._perform_deferred_updates()

        self.assertIsNotNone(window.amplitude_widget.current_data)
        self.assertIsNotNone(window.phase_widget.current_data)


if __name__ == "__main__":
    unittest.main()
