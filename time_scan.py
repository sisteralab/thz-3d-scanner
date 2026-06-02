import json
import time
from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from api.vna import VNABlock


SCAN_DURATION_S = 3600.0
DEFAULT_DISPLAY_POINTS = 2000


def save_data(data):
    filename = f"meas_time_scan{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)
    return filename


def configure_vna(vna):
    vna.set_parameter("BA")
    vna.set_start_time(0)
    vna.set_stop_time(50e-3)
    vna.set_sweep(100)
    vna.set_power(-30)
    vna.set_channel_format("COMP")
    vna.set_average_status(False)
    vna.set_bandwidth(10000)


class TimeScanThread(QThread):
    point_ready = Signal(dict)
    error = Signal(str)

    def __init__(self, vna, stop_time=SCAN_DURATION_S, parent=None):
        super().__init__(parent)
        self.vna = vna
        self.stop_time = float(stop_time)
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        start_time = time.time()
        while self._running:
            elapsed = time.time() - start_time
            if elapsed >= self.stop_time:
                break

            try:
                data = self.vna.get_data()
            except Exception as err:
                self.error.emit(str(err))
                break

            real = np.asarray(data.get("real", []), dtype=np.float32)
            imag = np.asarray(data.get("imag", []), dtype=np.float32)
            points_count = int(min(real.size, imag.size))
            if points_count == 0:
                continue

            mean_real = float(np.mean(real[:points_count], dtype=np.float64))
            mean_imag = float(np.mean(imag[:points_count], dtype=np.float64))
            amplitude = float(20 * np.log10(max(np.hypot(mean_real, mean_imag), 1e-12)))
            phase = float(np.arctan2(mean_imag, mean_real))
            elapsed = time.time() - start_time

            self.point_ready.emit(
                {
                    "real": mean_real,
                    "imag": mean_imag,
                    "amplitude": amplitude,
                    "phase": phase,
                    "time": elapsed,
                }
            )


class TimeScanWindow(QWidget):
    def __init__(self, vna, stop_time=SCAN_DURATION_S):
        super().__init__()
        self.setWindowTitle("Time Scan")
        self.resize(1000, 700)

        self.full_data = []
        self.times = []
        self.amplitudes = []
        self.phases = []
        self.phase_degrees = []
        self._last_raw_phase = None
        self._phase_unwrap_offset = 0.0
        self._saved = False
        self._follow_latest_count = True

        layout = QVBoxLayout(self)
        self.status_label = QLabel("Time scan running")

        display_layout = QHBoxLayout()
        latest_count_label = QLabel("Latest count:")
        self.display_points_spin = QSpinBox()
        self.display_points_spin.setRange(1, 1_000_000)
        self.display_points_spin.setValue(DEFAULT_DISPLAY_POINTS)
        self.display_points_spin.setSingleStep(100)
        self.display_points_spin.setToolTip(
            "Only this many latest points are drawn. All measured points are still saved."
        )
        from_label = QLabel("From point:")
        self.display_from_spin = QSpinBox()
        self.display_from_spin.setRange(1, 1_000_000)
        self.display_from_spin.setValue(1)
        self.display_from_spin.setToolTip("First point index to draw, starting from 1.")

        to_label = QLabel("To point:")
        self.display_to_spin = QSpinBox()
        self.display_to_spin.setRange(0, 1_000_000)
        self.display_to_spin.setSpecialValueText("latest")
        self.display_to_spin.setValue(0)
        self.display_to_spin.setToolTip(
            "Last point index to draw. Use 'latest' to follow new points live."
        )

        display_layout.addWidget(latest_count_label)
        display_layout.addWidget(self.display_points_spin)
        display_layout.addWidget(from_label)
        display_layout.addWidget(self.display_from_spin)
        display_layout.addWidget(to_label)
        display_layout.addWidget(self.display_to_spin)
        display_layout.addStretch(1)

        self.amplitude_plot = pg.PlotWidget(title="Amplitude vs Time")
        self.phase_plot = pg.PlotWidget(title="Phase vs Time")
        for plot in (self.amplitude_plot, self.phase_plot):
            plot.setBackground("w")
            plot.showGrid(x=True, y=True, alpha=0.3)
            plot.setLabel("bottom", "Time", units="s")

        self.amplitude_plot.setLabel("left", "Amplitude", units="dB")
        self.phase_plot.setLabel("left", "Phase", units="deg")

        self.amplitude_curve = self.amplitude_plot.plot(
            pen=pg.mkPen((220, 40, 40), width=2)
        )
        self.phase_curve = self.phase_plot.plot(pen=pg.mkPen((40, 90, 220), width=2))

        buttons_layout = QHBoxLayout()
        self.stop_button = QPushButton("Stop")
        self.save_button = QPushButton("Save")
        buttons_layout.addWidget(self.stop_button)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addStretch(1)

        layout.addWidget(self.status_label)
        layout.addLayout(display_layout)
        layout.addWidget(self.amplitude_plot)
        layout.addWidget(self.phase_plot)
        layout.addLayout(buttons_layout)

        self.thread = TimeScanThread(vna, stop_time, self)
        self.thread.point_ready.connect(self._append_point)
        self.thread.error.connect(self._on_error)
        self.thread.finished.connect(self._on_finished)
        self.stop_button.clicked.connect(self._stop_scan)
        self.save_button.clicked.connect(self._save)
        self.display_points_spin.valueChanged.connect(self._on_latest_count_changed)
        self.display_from_spin.valueChanged.connect(self._on_display_range_changed)
        self.display_to_spin.valueChanged.connect(self._on_display_range_changed)
        self.thread.start()

    def _append_point(self, point):
        self.full_data.append(point)
        self.times.append(float(point["time"]))
        self.amplitudes.append(float(point["amplitude"]))
        raw_phase = float(point["phase"])
        unwrapped_phase = self._unwrap_phase(raw_phase)
        phase_degrees = float(np.degrees(unwrapped_phase))
        point["phase_deg"] = float(np.degrees(raw_phase))
        point["phase_unwrapped_deg"] = phase_degrees
        self.phases.append(raw_phase)
        self.phase_degrees.append(phase_degrees)

        if self._follow_latest_count:
            self._apply_latest_count_range()
        self._update_plot_data()
        self.status_label.setText(
            f"Samples: {len(self.full_data)} | "
            f"displayed: {self._displayed_points_count()} | "
            f"t={self.times[-1]:.2f}s | "
            f"amp={self.amplitudes[-1]:.3f} dB | "
            f"phase={self.phase_degrees[-1]:.2f} deg"
        )

    def _unwrap_phase(self, raw_phase):
        if self._last_raw_phase is None:
            self._last_raw_phase = raw_phase
            return raw_phase

        delta = raw_phase - self._last_raw_phase
        if delta > np.pi:
            self._phase_unwrap_offset -= 2 * np.pi
        elif delta < -np.pi:
            self._phase_unwrap_offset += 2 * np.pi
        self._last_raw_phase = raw_phase
        return raw_phase + self._phase_unwrap_offset

    def _on_latest_count_changed(self, value):
        self._follow_latest_count = True
        self._apply_latest_count_range()
        self._update_plot_data()

    def _on_display_range_changed(self, _value):
        self._follow_latest_count = False
        self._update_plot_data()

    def _apply_latest_count_range(self):
        total_points = len(self.full_data)
        if total_points <= 0:
            return

        start_point = max(1, total_points - int(self.display_points_spin.value()) + 1)
        self.display_from_spin.blockSignals(True)
        self.display_to_spin.blockSignals(True)
        self.display_from_spin.setValue(start_point)
        self.display_to_spin.setValue(0)
        self.display_from_spin.blockSignals(False)
        self.display_to_spin.blockSignals(False)

    def _display_range_indices(self):
        total_points = len(self.times)
        if total_points == 0:
            return 0, 0

        start_point = int(self.display_from_spin.value())
        end_point = int(self.display_to_spin.value())
        if end_point == 0:
            end_point = total_points

        start_point = int(np.clip(start_point, 1, total_points))
        end_point = int(np.clip(end_point, 1, total_points))
        if end_point < start_point:
            start_point, end_point = end_point, start_point

        return start_point - 1, end_point

    def _displayed_points_count(self):
        start_idx, end_idx = self._display_range_indices()
        return max(0, end_idx - start_idx)

    def _update_plot_data(self):
        start_idx, end_idx = self._display_range_indices()
        times = self.times[start_idx:end_idx]
        amplitudes = self.amplitudes[start_idx:end_idx]
        phases = self.phase_degrees[start_idx:end_idx]
        self.amplitude_curve.setData(times, amplitudes)
        self.phase_curve.setData(times, phases)

    def _on_error(self, message):
        self.status_label.setText(f"Time scan error: {message}")
        self._save()

    def _on_finished(self):
        if self.full_data:
            self._save()
        self.stop_button.setEnabled(False)
        self.status_label.setText(f"{self.status_label.text()} | stopped")

    def _stop_scan(self):
        self.thread.stop()
        self.stop_button.setEnabled(False)

    def _save(self):
        if self._saved or not self.full_data:
            return
        filename = save_data(self.full_data)
        self._saved = True
        self.status_label.setText(f"{self.status_label.text()} | saved: {filename}")

    def closeEvent(self, event):
        if self.thread.isRunning():
            self.thread.stop()
            self.thread.wait(3000)
        if self.full_data:
            self._save()
        event.accept()


def main():
    app = QApplication([])
    vna = VNABlock()
    configure_vna(vna)

    window = TimeScanWindow(vna)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
