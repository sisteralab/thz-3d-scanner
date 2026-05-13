import psutil
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer


class MemoryMonitor(QLabel):
    """Widget to display real-time memory usage."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("color: #555; font-size: 11px;")
        self.setText("Memory: 0 MB / 0 MB")
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update_memory)
        self._timer.start(1000)  # Update every second

    def update_memory(self):
        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            mem_used_mb = mem_info.rss / (1024 * 1024)
            mem_available_mb = psutil.virtual_memory().available / (1024 * 1024)
            self.setText(
                f"Memory: {mem_used_mb:.1f} MB / {mem_available_mb:.1f} MB available"
            )
        except Exception:
            self.setText("Memory: N/A")
