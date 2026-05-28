import sys

from PySide6.QtCore import QLoggingCategory
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
import pyqtgraph as pg

from utils.resources import asset_path


if __name__ == "__main__":
    QLoggingCategory.setFilterRules("qt.pointer.dispatch=false")
    app = QApplication(sys.argv)
    app_icon = QIcon(asset_path("scanner3d.ico"))
    app.setWindowIcon(app_icon)

    # Optimize PyQtGraph for NumPy compatibility and performance
    pg.setConfigOption(
        "imageAxisOrder", "row-major"
    )  # Match NumPy's default (row-major)
    pg.setConfigOptions(antialias=False)  # Disable anti-aliasing for speed

    # Import after QApplication is created to avoid potential compatibility issues
    from interface.index import MainWindow

    window = MainWindow()
    window.setWindowIcon(app_icon)

    window.show()
    sys.exit(app.exec())
