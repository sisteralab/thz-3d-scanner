import uuid
from typing import Optional
import json
import logging

from PySide6 import QtGui, QtWidgets, QtCore
from PySide6.QtWidgets import (
    QAbstractItemView,
    QMessageBox,
    QWidget,
    QVBoxLayout,
    QHeaderView,
)
from PySide6.QtGui import QAction

from constants import DataTableColumns
from interface.comment_dialog import CommentDialogBox
from interface.plot_widgets import DataVisualizationWindow
from store.data import MeasureTableModel, MeasureManager, MeasureModel

logger = logging.getLogger(__name__)


class TableView(QtWidgets.QTableView):
    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.menu = QtWidgets.QMenu(self)

        self.visualisation_windows = {}

        self.action_comment = QtWidgets.QWidgetAction(self)
        self.action_save = QtWidgets.QWidgetAction(self)
        self.action_delete = QtWidgets.QWidgetAction(self)

        self.action_comment.setText("Comment")
        self.action_save.setText("Save")
        self.action_delete.setText("Delete")

        self.action_comment.setIcon(QtGui.QIcon("assets/edit-icon.png"))
        self.action_save.setIcon(QtGui.QIcon("assets/save-icon.png"))
        self.action_delete.setIcon(QtGui.QIcon("assets/delete-icon.png"))
        self.action_build = QAction("Build", self)
        self.action_build.setIcon(QtGui.QIcon("assets/yes-icon.png"))

        self.menu.addAction(self.action_comment)
        self.menu.addAction(self.action_save)
        self.menu.addAction(self.action_build)
        self.menu.addAction(self.action_delete)

        self.action_comment.triggered.connect(self.commentSelectedRow)
        self.action_save.triggered.connect(self.saveSelectedRow)
        self.action_build.triggered.connect(self.buildSelectedRow)
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

    def buildSelectedRow(self):
        """Build visualization windows for selected data"""
        model = self.model()
        selection = self.selectionModel()
        rows = list(set(index.row() for index in selection.selectedIndexes()))
        if not len(rows):
            return

        # Get the selected measure model
        row = rows[0]
        measure = model.manager.all()[row]

        # Check if data is a dictionary or list of dictionaries
        data = measure.data
        if not data:
            return

        if isinstance(data, dict):
            # Single data dictionary - open one window
            self.open_visualization_window(data, measure.comment)
        elif isinstance(data, list):
            # List of data dictionaries - open multiple windows
            for single_data in data:
                self.open_visualization_window(single_data, measure.comment)

    def open_visualization_window(self, data, comment: str = ""):
        """Open a visualization window for the given data"""
        try:
            # Create and show the visualization window
            window = DataVisualizationWindow(data, comment)
            self.visualisation_windows[uuid.uuid4()] = window
            window.show()
        except Exception as e:
            logger.exception(f"Error opening visualization window: {e}")


class DataTable(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)

        # Add import button
        self.import_button = QtWidgets.QPushButton("Import Data")
        self.layout.addWidget(self.import_button)

        self.tableView = None
        self.model = None
        self.createTableView()
        self.layout.addWidget(self.tableView)

        # Connect button after methods are defined
        self.import_button.clicked.connect(self.import_data)

    def import_data(self):
        """Import data from file and add to table"""
        logger = logging.getLogger(__name__)
        logger.info("Starting data import process")

        # Open file dialog to select JSON file
        file_dialog = QtWidgets.QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Import Measurement Data", "", "JSON Files (*.json);;All Files (*)"
        )

        if not file_path:
            logger.info("Import cancelled by user")
            return

        try:
            logger.info(f"Importing data from file: {file_path}")

            # Read and parse the JSON file
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            logger.info(f"Successfully parsed JSON data: {type(data)}")

            # Validate and import the data
            self.process_imported_data(data)

            logger.info("Data import completed successfully")
            QtWidgets.QMessageBox.information(
                self, "Import Successful", "Data imported successfully!"
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Import Error", f"Invalid JSON format: {str(e)}"
            )
        except FileNotFoundError as e:
            logger.error(f"File not found: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Import Error", f"File not found: {str(e)}"
            )
        except PermissionError as e:
            logger.error(f"Permission error: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self, "Import Error", f"Permission denied: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error during import: {str(e)}", exc_info=True)
            QtWidgets.QMessageBox.critical(
                self, "Import Error", f"Failed to import data: {str(e)}"
            )

    def process_imported_data(self, data):
        """Process imported data and create new measure records"""
        logger = logging.getLogger(__name__)
        logger.info(f"Processing imported data of type: {type(data)}")

        if isinstance(data.get("data"), list):
            # Single measurement record
            logger.info("Processing single measurement record")
            self.create_measure_from_data(data)
        else:
            logger.error(f"Unsupported data type: {type(data)}")
            raise ValueError(f"Unsupported data type: {type(data)}")

    def create_measure_from_data(self, data):
        """Create a new measure record from imported data"""
        logger = logging.getLogger(__name__)
        logger.info("Creating new measure from imported data")

        try:
            # Create new measure record
            new_measure = MeasureModel.objects.create(
                comment=data.get("comment"),
                data=data.get("data"),
            )
            logger.info(f"Created new measure with ID: {new_measure.id}")

            # Save the new measure
            new_measure.save(True)
            logger.info(f"Successfully saved measure {new_measure.id}")

        except Exception as e:
            logger.error(f"Failed to create/save measure: {str(e)}", exc_info=True)
            raise

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
