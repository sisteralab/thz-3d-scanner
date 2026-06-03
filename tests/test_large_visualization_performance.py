import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from application.visualization.plot_slicing import PLOT_PLANE_ZX, extract_axis_slice
from interface.plot_widgets import AmplitudePlotWidget, PhasePlotWidget
from store.state import State


class CoalescingRenderSink:
    def __init__(self, amplitude_widget, phase_widget):
        self.amplitude_widget = amplitude_widget
        self.phase_widget = phase_widget
        self.pending_data = None
        self.last_update_time = 0.0
        self.render_count = 0
        self.rendered_sequences = []
        self.timer = QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.apply_pending)

    def update_plot(self, data):
        self.pending_data = data
        if self.timer.isActive():
            return

        update_hz = max(0.01, float(getattr(State, "plot_update_hz", 10.0)))
        elapsed_ms = int((time.perf_counter() - self.last_update_time) * 1000)
        delay_ms = max(0, int(round(1000 / update_hz)) - elapsed_ms)
        self.timer.start(delay_ms)

    def apply_pending(self):
        if self.pending_data is None:
            return
        data = self.pending_data
        self.pending_data = None
        self.last_update_time = time.perf_counter()
        self.render_count += 1
        self.rendered_sequences.append(int(data.get("sequence", -1)))
        self.amplitude_widget.update_data(data)
        self.amplitude_widget._perform_deferred_updates()
        self.phase_widget.update_data(data)
        self.phase_widget._perform_deferred_updates()


class LargeVisualizationPerformanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_large_tensor_slice_and_render_smoke(self):
        State.plot_max_pixels = 0
        y_count, x_count, z_count = 8, 512, 512
        x_axis = np.linspace(-10.0, 10.0, x_count, dtype=np.float32)
        y_axis = np.linspace(-2.0, 2.0, y_count, dtype=np.float32)
        z_axis = np.linspace(-5.0, 5.0, z_count, dtype=np.float32)
        x_grid, z_grid = np.meshgrid(x_axis, z_axis, indexing="ij")
        base = np.sin(x_grid).astype(np.float32) + np.cos(z_grid).astype(np.float32)
        amplitude = np.empty((y_count, x_count, z_count), dtype=np.float32)
        phase = np.empty_like(amplitude)
        phase_degrees = np.empty_like(amplitude)
        for y_idx, y_value in enumerate(y_axis):
            amplitude[y_idx] = base + y_value
            phase[y_idx] = np.arctan2(z_grid, x_grid + np.float32(1e-3))
            phase_degrees[y_idx] = np.rad2deg(phase[y_idx]).astype(np.float32)

        payload = {
            "x": x_axis,
            "y": y_axis,
            "z": z_axis,
            "amplitude": amplitude,
            "phase": phase,
            "phase_degrees": phase_degrees,
            "late_sample": np.zeros_like(amplitude, dtype=bool),
            "has_late_samples": False,
        }

        started = time.perf_counter()
        sliced = extract_axis_slice(payload, PLOT_PLANE_ZX, y_count // 2)
        slice_ms = (time.perf_counter() - started) * 1000.0

        self.assertTrue(np.shares_memory(sliced["amplitude"], amplitude))

        amplitude_widget = AmplitudePlotWidget()
        phase_widget = PhasePlotWidget()

        render_times = []
        started = time.perf_counter()
        for _ in range(6):
            frame_started = time.perf_counter()
            amplitude_widget.update_data(sliced)
            amplitude_widget._perform_deferred_updates()
            phase_widget.update_data(sliced)
            phase_widget._perform_deferred_updates()
            self.app.processEvents()
            render_times.append((time.perf_counter() - frame_started) * 1000.0)
        render_ms = (time.perf_counter() - started) * 1000.0
        steady_render_ms = sum(render_times[2:]) / max(1, len(render_times[2:]))

        print(
            "large visualization metrics: "
            f"points={amplitude.size}, slice_ms={slice_ms:.2f}, "
            f"first_pair_render_ms={render_times[0]:.2f}, "
            f"steady_pair_render_ms={steady_render_ms:.2f}, "
            f"total_render_ms={render_ms:.2f}"
        )
        self.assertLess(slice_ms, 100.0)
        self.assertLess(steady_render_ms, 100.0)

    def test_full_resolution_1000x1000_pair_render_steady_state(self):
        State.plot_max_pixels = 0
        size = 1000
        x_axis = np.linspace(-10.0, 10.0, size, dtype=np.float32)
        z_axis = np.linspace(-5.0, 5.0, size, dtype=np.float32)
        x_grid, z_grid = np.meshgrid(x_axis, z_axis, indexing="ij")
        amplitude = (np.sin(x_grid) + np.cos(z_grid)).astype(np.float32)
        phase = np.arctan2(z_grid, x_grid + np.float32(1e-3)).astype(np.float32)
        payload = {
            "x": x_axis,
            "z": z_axis,
            "amplitude": amplitude,
            "phase": phase,
            "phase_degrees": np.rad2deg(phase).astype(np.float32),
            "late_sample": np.zeros_like(amplitude, dtype=bool),
            "has_late_samples": False,
            "horizontal_axis_name": "X",
            "vertical_axis_name": "Z",
        }

        amplitude_widget = AmplitudePlotWidget()
        phase_widget = PhasePlotWidget()
        render_times = []
        for _ in range(8):
            started = time.perf_counter()
            amplitude_widget.update_data(payload)
            amplitude_widget._perform_deferred_updates()
            phase_widget.update_data(payload)
            phase_widget._perform_deferred_updates()
            self.app.processEvents()
            render_times.append((time.perf_counter() - started) * 1000.0)

        steady_render_ms = sum(render_times[2:]) / max(1, len(render_times[2:]))
        print(
            "1000x1000 full-resolution pair render metrics: "
            f"first_ms={render_times[0]:.2f}, steady_ms={steady_render_ms:.2f}"
        )
        self.assertLess(steady_render_ms, 8.0)

    def test_full_resolution_1000x1000_with_calibrated_data_and_late_mask(self):
        State.plot_max_pixels = 0
        size = 1000
        x_axis = np.linspace(-10.0, 10.0, size, dtype=np.float32)
        z_axis = np.linspace(-5.0, 5.0, size, dtype=np.float32)
        x_grid, z_grid = np.meshgrid(x_axis, z_axis, indexing="ij")
        amplitude = (np.sin(x_grid) + np.cos(z_grid)).astype(np.float32)
        phase = np.arctan2(z_grid, x_grid + np.float32(1e-3)).astype(np.float32)
        late_mask = np.zeros_like(amplitude, dtype=bool)
        late_mask.ravel()[::100] = True
        payload = {
            "x": x_axis,
            "z": z_axis,
            "amplitude": amplitude + np.float32(0.25),
            "phase": phase,
            "phase_degrees": np.rad2deg(phase).astype(np.float32),
            "complex_real": np.cos(phase).astype(np.float32),
            "complex_imag": np.sin(phase).astype(np.float32),
            "calibrated_amplitude": amplitude + np.float32(0.5),
            "calibrated_phase": phase,
            "calibrated_phase_degrees": np.rad2deg(phase).astype(np.float32),
            "calibrated_complex_real": np.cos(phase).astype(np.float32),
            "calibrated_complex_imag": np.sin(phase).astype(np.float32),
            "late_sample": late_mask,
            "has_late_samples": True,
            "horizontal_axis_name": "X",
            "vertical_axis_name": "Z",
            "display_calibrated": True,
        }

        amplitude_widget = AmplitudePlotWidget()
        phase_widget = PhasePlotWidget()
        render_times = []
        for _ in range(8):
            started = time.perf_counter()
            amplitude_widget.update_data(payload)
            amplitude_widget._perform_deferred_updates()
            phase_widget.update_data(payload)
            phase_widget._perform_deferred_updates()
            self.app.processEvents()
            render_times.append((time.perf_counter() - started) * 1000.0)

        steady_render_ms = sum(render_times[2:]) / max(1, len(render_times[2:]))
        print(
            "1000x1000 calibrated+late-mask pair render metrics: "
            f"first_ms={render_times[0]:.2f}, steady_ms={steady_render_ms:.2f}"
        )
        self.assertLess(steady_render_ms, 12.0)

    def test_gui_render_does_not_delay_fake_measurement_loop(self):
        State.plot_max_pixels = 0
        point_spacing_mm = 0.5
        motor_speed_mm_s = 5.0
        vna_latency_s = 0.1
        target_period_s = point_spacing_mm / motor_speed_mm_s
        point_count = 12

        x_count, z_count = 512, 512
        x_axis = np.linspace(-10.0, 10.0, x_count, dtype=np.float32)
        z_axis = np.linspace(-5.0, 5.0, z_count, dtype=np.float32)
        x_grid, z_grid = np.meshgrid(x_axis, z_axis, indexing="ij")
        amplitude = (np.sin(x_grid) + np.cos(z_grid)).astype(np.float32)
        phase = np.arctan2(z_grid, x_grid + np.float32(1e-3)).astype(np.float32)
        payload = {
            "x": x_axis,
            "z": z_axis,
            "amplitude": amplitude,
            "phase": phase,
            "phase_degrees": np.rad2deg(phase).astype(np.float32),
            "late_sample": np.zeros_like(amplitude, dtype=bool),
            "has_late_samples": False,
            "horizontal_axis_name": "X",
            "vertical_axis_name": "Z",
        }

        timestamps = []
        stop_event = threading.Event()

        def fake_measurement_loop():
            for _ in range(point_count):
                started = time.perf_counter()
                time.sleep(vna_latency_s)
                timestamps.append(time.perf_counter())
                sleep_left = max(0.0, target_period_s - (time.perf_counter() - started))
                if sleep_left:
                    time.sleep(sleep_left)
            stop_event.set()

        worker = threading.Thread(target=fake_measurement_loop)
        amplitude_widget = AmplitudePlotWidget()
        phase_widget = PhasePlotWidget()
        worker.start()

        render_times = []
        while not stop_event.is_set():
            frame_started = time.perf_counter()
            amplitude_widget.update_data(payload)
            amplitude_widget._perform_deferred_updates()
            phase_widget.update_data(payload)
            phase_widget._perform_deferred_updates()
            self.app.processEvents()
            render_times.append((time.perf_counter() - frame_started) * 1000.0)

        worker.join(timeout=1.0)
        intervals = np.diff(np.asarray(timestamps, dtype=np.float64))
        max_interval_s = float(np.max(intervals)) if intervals.size else 0.0
        avg_render_ms = sum(render_times) / max(1, len(render_times))

        print(
            "measurement/gui contention metrics: "
            f"target_period_ms={target_period_s * 1000.0:.1f}, "
            f"max_measure_interval_ms={max_interval_s * 1000.0:.1f}, "
            f"avg_pair_render_ms={avg_render_ms:.2f}, "
            f"render_frames={len(render_times)}"
        )
        self.assertEqual(len(timestamps), point_count)
        self.assertLess(max_interval_s, target_period_s + 0.03)

    def test_per_point_preview_at_60hz_for_100ms_points(self):
        State.plot_max_pixels = 0
        State.plot_update_hz = 60.0
        size = 512
        x_axis = np.linspace(-10.0, 10.0, size, dtype=np.float32)
        z_axis = np.linspace(-5.0, 5.0, size, dtype=np.float32)
        x_grid, z_grid = np.meshgrid(x_axis, z_axis, indexing="ij")
        amplitude = (np.sin(x_grid) + np.cos(z_grid)).astype(np.float32)
        phase = np.arctan2(z_grid, x_grid + np.float32(1e-3)).astype(np.float32)
        payload = {
            "x": x_axis,
            "z": z_axis,
            "amplitude": amplitude,
            "phase": phase,
            "phase_degrees": np.rad2deg(phase).astype(np.float32),
            "has_late_samples": False,
            "horizontal_axis_name": "X",
            "vertical_axis_name": "Z",
        }
        sink = CoalescingRenderSink(AmplitudePlotWidget(), PhasePlotWidget())

        point_count = 10
        point_period_s = 0.1
        started = time.perf_counter()
        for sequence in range(point_count):
            payload["sequence"] = sequence
            sink.update_plot(payload)
            deadline = started + (sequence + 1) * point_period_s
            while time.perf_counter() < deadline:
                self.app.processEvents()
                time.sleep(0.001)
        for _ in range(30):
            self.app.processEvents()
            time.sleep(0.001)

        print(
            "per-point 60hz preview metrics: "
            f"points={point_count}, rendered={sink.render_count}, "
            f"last_sequence={sink.rendered_sequences[-1] if sink.rendered_sequences else None}"
        )
        self.assertGreaterEqual(sink.render_count, point_count - 1)
        self.assertEqual(sink.rendered_sequences[-1], point_count - 1)

    def test_fast_per_point_preview_coalesces_to_latest_frame(self):
        State.plot_max_pixels = 0
        State.plot_update_hz = 60.0
        size = 512
        x_axis = np.linspace(-10.0, 10.0, size, dtype=np.float32)
        z_axis = np.linspace(-5.0, 5.0, size, dtype=np.float32)
        x_grid, z_grid = np.meshgrid(x_axis, z_axis, indexing="ij")
        amplitude = (np.sin(x_grid) + np.cos(z_grid)).astype(np.float32)
        phase = np.arctan2(z_grid, x_grid + np.float32(1e-3)).astype(np.float32)
        payload = {
            "x": x_axis,
            "z": z_axis,
            "amplitude": amplitude,
            "phase": phase,
            "phase_degrees": np.rad2deg(phase).astype(np.float32),
            "has_late_samples": False,
            "horizontal_axis_name": "X",
            "vertical_axis_name": "Z",
        }
        sink = CoalescingRenderSink(AmplitudePlotWidget(), PhasePlotWidget())

        event_count = 120
        for sequence in range(event_count):
            payload["sequence"] = sequence
            sink.update_plot(payload)
            self.app.processEvents()

        for _ in range(80):
            self.app.processEvents()
            time.sleep(0.001)

        print(
            "fast per-point coalescing metrics: "
            f"events={event_count}, rendered={sink.render_count}, "
            f"last_sequence={sink.rendered_sequences[-1] if sink.rendered_sequences else None}"
        )
        self.assertLess(sink.render_count, event_count)
        self.assertEqual(sink.rendered_sequences[-1], event_count - 1)


if __name__ == "__main__":
    unittest.main()
