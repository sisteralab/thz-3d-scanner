import numpy as np
import pyqtgraph.opengl as gl
from PySide6 import QtGui
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from interface.manager_widget import ManagerWidget
from store.state import State


def cet_l4(z):
    """poor approximation of the `CET-L4` colormap"""
    z_min, z_range = z.min(), z.ptp()
    return [
        1.5 / z_range,
        -z_min,
        0.7,  # red channel
        1.7 / z_range,
        -(z_min + 0.4 * z_range),
        1,  # green channel
        0,
        0,
        1,  # blue channel is empty
    ]


class Scanner3D(QMainWindow):
    def __init__(self):
        super().__init__()
        State.init_d3()
        State.init_vna()
        self.setWindowTitle("Scanner 3D")
        self.setGeometry(100, 100, 1200, 600)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QHBoxLayout(self.central_widget)

        self.manager_widget = ManagerWidget(self)

        self.plot_widget = gl.GLViewWidget()
        self.plot_widget.setBackgroundColor("w")
        self.plot_item = gl.GLSurfacePlotItem(
            smooth=False, computeNormals=False, shader="heightColor"
        )
        self.plot_widget.addItem(self.plot_item)

        # Добавление сетки
        gy = gl.GLGridItem(color="grey")
        gy.rotate(90, 1, 0, 0)
        self.plot_widget.addItem(gy)

        self.layout.addWidget(self.plot_widget)
        self.layout.addWidget(self.manager_widget)

        self.update_plot(
            {
                "amplitude": [
                    [-1, 0, 0, -1],
                    [-1, 0, 0, -1],
                    [-1, 0, 0, -1],
                    [-1, 0, 0, -1],
                ],
                "x": [-20, -10, 10, 20],
                "y": [-20, -10, 10, 20],
                "z": [-20, -10, 10, 20],
            }
        )

    def update_plot(self, data):
        x_data = np.array(data["x"])
        z_data = np.array(data["z"])
        amplitude = np.array(data["amplitude"])
        self.plot_item.setData(x=x_data, y=z_data, z=amplitude)
        self.plot_item.shader()["colorMap"] = cet_l4(amplitude)

    def closeEvent(self, event: QtGui.QCloseEvent):
        State.del_d3()
        State.del_vna()
        event.accept()
