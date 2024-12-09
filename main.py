import sys
from PySide6.QtWidgets import QApplication



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Scanner3D()
    window.show()
    sys.exit(app.exec())
