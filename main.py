import sys

from PySide6.QtCore import QLoggingCategory
from PySide6.QtWidgets import QApplication

if __name__ == "__main__":
    QLoggingCategory.setFilterRules("qt.pointer.dispatch=false")
    app = QApplication(sys.argv)

    # Import after QApplication is created to avoid potential compatibility issues
    from interface.index import MainWindow

    window = MainWindow()

    window.show()
    sys.exit(app.exec())
