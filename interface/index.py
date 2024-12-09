import numpy as np
from PySide6 import QtGui
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout
import pyqtgraph.opengl as gl
import pyqtgraph as pg

from interface.manager_widget import ManagerWidget
from store.state import State


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
        self.plot_widget.setBackgroundColor('w')

        self.layout.addWidget(self.plot_widget)
        self.layout.addWidget(self.manager_widget)

        # preparing plot

        self.plot_item = gl.GLSurfacePlotItem(shader='heightColor', computeNormals=False, smooth=False)
        self.plot_widget.addItem(self.plot_item)
        self.prepare_plot()
        # self.color_map = np.array([
        #     [0, 0, 1, 1],  # Синий
        #     [1, 0, 0, 1]  # Красный
        # ])
        # self.plot_item.shader()['colorMap'] = self.color_map


    def prepare_plot(self):
        # Добавление сетки
        self.grid = gl.GLGridItem(color='grey')
        self.plot_widget.addItem(self.grid)

        # Добавление подписей к осям
        self.x_label = gl.GLTextItem(pos=(10, 0, 0), text='X')
        self.y_label = gl.GLTextItem(pos=(0, 10, 0), text='Y')
        self.z_label = gl.GLTextItem(pos=(0, 0, 10), text='Z')
        self.plot_widget.addItem(self.x_label)
        self.plot_widget.addItem(self.y_label)
        self.plot_widget.addItem(self.z_label)

    def update_plot(self, data):
        z = np.array(data['amplitude'])
        cmap = pg.colormap.get('CET-L4')
        c = cmap.map((z - z.min()) / z.ptp(), cmap.FLOAT)
        self.plot_item.setData(x=np.array(data['x']), y=np.array(data['z']), z=z, colors=c)
        # x = np.linspace(-10, 10, 100)
        # y = np.linspace(-10, 10, 100)
        # z = np.sin(np.sqrt(x[:, np.newaxis] ** 2 + y[np.newaxis, :] ** 2 + np.random.rand() * 10))
        # self.plot_item.setData(x=x, y=y, z=z)

    def closeEvent(self, event: QtGui.QCloseEvent):
        State.del_d3()
        State.del_vna()
        event.accept()
