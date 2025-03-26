from typing import Optional

from PySide6 import QtGui, QtWidgets, QtCore
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QHeaderView,
)

from constants import DataTableColumns
from interface.comment_dialog import CommentDialogBox
from store.data import MeasureTableModel, MeasureManager, MeasureModel


class TableView(QtWidgets.QTableView):
    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.menu = QtWidgets.QMenu(self)

        self.action_comment = QtWidgets.QWidgetAction(self)
        self.action_save = QtWidgets.QWidgetAction(self)
        self.action_delete = QtWidgets.QWidgetAction(self)

        self.action_comment.setText("Comment")
        self.action_save.setText("Save")
        self.action_delete.setText("Delete")

        self.action_comment.setIcon(QtGui.QIcon("assets/edit-icon.png"))
        self.action_save.setIcon(QtGui.QIcon("assets/save-icon.png"))
        self.action_delete.setIcon(QtGui.QIcon("assets/delete-icon.png"))

        self.menu.addAction(self.action_comment)
        self.menu.addAction(self.action_save)
        self.menu.addAction(self.action_delete)

        self.action_comment.triggered.connect(self.commentSelectedRow)
        self.action_save.triggered.connect(self.saveSelectedRow)
        self.action_delete.triggered.connect(self.deleteSelectedRows)
        self.customContextMenuRequested.connect(self.showContextMenu)

    def showContextMenu(self, pos: QtCore.QPoint):
        self.menu.exec(self.mapToGlobal(pos))

    def saveSelectedRow(self):
        model = self.model()
        selection = self.selectionModel()
        rows = list(set(index.row() for index in selection.selectedIndexes()))
        if not len(rows):
            return
        model.manager.save_by_index(rows[0])

    def get_selected_measure_model(self) -> Optional[MeasureModel]:
        model = self.model()
        selection = self.selectionModel()
        selected_index = list(set(index for index in selection.selectedIndexes()))
        if not len(selected_index):
            return
        selected_index = selected_index[0]
        measure_model_id = selected_index.model()._data[selected_index.row()][0]
        return model.manager.get(id=measure_model_id)

    def commentSelectedRow(self):
        measure_model = self.get_selected_measure_model()
        if not measure_model:
            return
        reply = CommentDialogBox(self, measure_model.comment)
        button = reply.exec()
        if button == 1:
            measure_model.comment = reply.commentEdit.toPlainText()
            measure_model.objects.update_table()

    def deleteSelectedRows(self):
        model = self.model()
        selection = self.selectionModel()
        row = list(set(index.row() for index in selection.selectedIndexes()))
        if not len(row):
            return
        row = row[0]
        measure = model.manager.all()[row]

        dlg = QMessageBox(self)
        dlg.setWindowTitle("Deleting data")
        dlg.setText(f"Аre you sure you want to delete the data {measure.id}")
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        dlg.setIcon(QMessageBox.Icon.Question)
        button = dlg.exec()

        if button == QMessageBox.StandardButton.Yes:
            model.manager.delete_by_index(row)
        else:
            return


class DataTable(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        self.tableView = None
        self.model = None
        self.createTableView()
        self.layout.addWidget(self.tableView)

    def createTableView(self):
        self.tableView = TableView(self)

        self.model = MeasureTableModel()
        MeasureManager.table = self.model
        self.tableView.setModel(self.model)

        self.tableView.setColumnWidth(DataTableColumns.ID.index, 30)
        self.tableView.setColumnWidth(DataTableColumns.SAVED.index, 60)
        header = self.tableView.horizontalHeader()
        for col in DataTableColumns:
            if col in (DataTableColumns.ID, DataTableColumns.SAVED):
                continue
            header.setSectionResizeMode(col.index, QHeaderView.Stretch)

        self.tableView.verticalHeader().setVisible(False)
