import sys

from PySide6.QtCore import QLoggingCategory
from PySide6.QtWidgets import QApplication
import pyqtgraph as pg

if __name__ == "__main__":
    QLoggingCategory.setFilterRules("qt.pointer.dispatch=false")
    app = QApplication(sys.argv)

    # Optimize PyQtGraph for NumPy compatibility and performance
    pg.setConfigOption(
        "imageAxisOrder", "row-major"
    )  # Match NumPy's default (row-major)
    pg.setConfigOptions(antialias=False)  # Disable anti-aliasing for speed

    # Import after QApplication is created to avoid potential compatibility issues
    from interface.index import MainWindow

    window = MainWindow()

    window.show()
    sys.exit(app.exec())
