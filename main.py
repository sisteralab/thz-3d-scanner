import sys
from PySide6.QtWidgets import QApplication

from interface.index import Scanner3D


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Scanner3D()
    window.show()
    sys.exit(app.exec())
