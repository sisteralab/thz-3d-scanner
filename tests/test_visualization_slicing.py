import unittest

import numpy as np

from application.visualization.plot_slicing import (
    PLOT_PLANE_XY,
    PLOT_PLANE_ZX,
    extract_axis_slice,
    plot_slice_axis_name,
)
from interface.plot_widgets import BasePlotWidget, phase_rad_to_degrees
from store.state import State


class VisualizationSlicingTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
