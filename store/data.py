import json
import os
from datetime import datetime
from typing import Union, Dict, Any

import json
from PySide6 import QtGui
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PySide6.QtWidgets import QFileDialog

from constants import DataTableColumns


class MeasureList(list):
    def first(self) -> Union["MeasureModel", None]:
        try:
            return self[0]
        except IndexError:
            return None

    def last(self) -> Union["MeasureModel", None]:
        try:
            return self[-1]
        except IndexError:
            return None

    def _filter(self, **kwargs) -> filter:
        def _filter(item):
            for key, value in kwargs.items():
                if not getattr(item, key, None) == value:
                    return False
            return True

        return filter(_filter, self)

    def filter(self, **kwargs) -> "MeasureList":
        return self.__class__(self._filter(**kwargs))

    def delete_by_index(self, index: int) -> None:
        del self[index]


class MeasureManager:
    table: "MeasureTableModel" = None
    _instances: MeasureList = MeasureList()
    latest_id = 0

    @classmethod
    def create(cls, *args, **kwargs) -> "MeasureModel":
        instance = MeasureModel(*args, **kwargs)
        cls._instances.append(instance)
        return instance

    @classmethod
    def update_table(cls):
        if isinstance(cls.table, MeasureTableModel):
            cls.table.updateData()

    @classmethod
    def all(cls):
        return cls._instances

    @classmethod
    def count(cls):
        return len(cls._instances)

    @classmethod
    def filter(cls, **kwargs) -> MeasureList:
        return cls.all().filter(**kwargs)

    @classmethod
    def get(cls, **kwargs) -> Union["MeasureModel", None]:
        filtered = cls.filter(**kwargs)
        if len(filtered) == 0:
            return None
        return filtered[0]

    @classmethod
    def delete_by_index(cls, index: int) -> None:
        cls.all().delete_by_index(index)
        cls.update_table()

    @classmethod
    def save_by_index(cls, index: int) -> None:
        measure = cls.all()[index]
        results = measure.to_json()
        caption = f"Saving meeasure {measure.id}"
        try:
            filepath = QFileDialog.getSaveFileName(filter="*.json", caption=caption)[0]
            if not filepath:
                return
            if not filepath.endswith(".json"):
                filepath += ".json"
            with open(filepath, "w", encoding="utf-8") as file:
                json.dump(results, file, ensure_ascii=False, indent=4)
            measure.saved = True
            measure.save(finish=False)
        except (IndexError, FileNotFoundError):
            pass

    @classmethod
    def save_all(cls):
        data = [m.to_json() for m in cls.all()]
        if not data:
            return
        if not os.path.exists("dumps"):
            os.mkdir("dumps")
        filepath = f"dumps/dump_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json"
        with open(filepath, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)


class MeasureModel:
    objects = MeasureManager
    ind_attr_map = {
        0: "id",
        1: "comment",
        2: "started",
        3: "finished",
        4: "saved",
    }

    def __init__(
        self,
        data: Dict,
        finished: Any = "--",
        comment: str = "",
    ):
        self.data = data
        self.objects.latest_id += 1
        self.id = self.objects.latest_id
        self.started = datetime.now()
        self.finished = finished
        self.saved = False
        self.comment = comment

    def get_attr_by_ind(self, ind: int):
        attr = self.ind_attr_map.get(ind)
        if attr:
            return getattr(self, attr)

    def save(self, finish: bool = True):
        if finish:
            self.finished = datetime.now()
        self.objects.update_table()

    def to_json(self):
        finished = self.finished
        if finished == "--":
            finished = datetime.now()
        return {
            "id": self.id,
            "comment": self.comment,
            "started": self.started.strftime("%Y-%m-%d %H:%M:%S"),
            "finished": finished.strftime("%Y-%m-%d %H:%M:%S"),
            "data": self.data,
        }


class MeasureTableModel(QAbstractTableModel):
    manager = MeasureManager

    def __init__(self, data=None):
        super().__init__()
        self._data = []
        self._headers = DataTableColumns.get_all_names()

    def data(self, index, role):
        if not self._data:
            return None
        value = self._data[index.row()][index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            if isinstance(value, datetime):
                return value.strftime("%H:%M:%S")
            return value
        if role == Qt.ItemDataRole.DecorationRole:
            if isinstance(value, bool):
                if value:
                    return QtGui.QIcon("assets/yes-icon.png")
                return QtGui.QIcon("assets/no-icon.png")
            return value
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

    def setData(self, index: QModelIndex, value: Any, role: int = ...) -> bool:
        if index.isValid() and role == Qt.ItemDataRole.EditRole:
            row = index.row()
            col = index.column()
            self._data[row][col] = value
            self.dataChanged.emit(index, index)
            return True
        return False

    def updateData(self):
        self.beginResetModel()
        measures = self.manager.all()
        self._data = [
            [m.id, m.comment, m.started, m.finished, m.saved] for m in measures
        ]
        self.endResetModel()

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._headers[section])
            elif orientation == Qt.Orientation.Vertical:
                return str(section + 1)
        return None

    def rowCount(self, index):
        # The length of the outer list.
        return len(self._data)

    def columnCount(self, index):
        return len(MeasureModel.ind_attr_map)


if __name__ == "__main__":
    d = MeasureModel.objects.create(data={})
    print(MeasureModel.objects.filter(measure_type="iv_curve"))
