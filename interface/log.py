import logging

from PySide6 import QtWidgets
from PySide6.QtCore import Qt


class LogWidget(QtWidgets.QGroupBox):
    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Log")
        self.setMaximumHeight(150)
        self.setMinimumWidth(400)

        layout = QtWidgets.QHBoxLayout()
        self.content = QtWidgets.QTextEdit(self)
        self.content.setReadOnly(True)
        self.content.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )

        self.btn_clear = QtWidgets.QPushButton("Clear", self)
        self.btn_clear.clicked.connect(self.clear_log)

        layout.addWidget(self.content)
        layout.addWidget(self.btn_clear, alignment=Qt.AlignRight)
        self.setLayout(layout)

    def set_log(self, text: str):
        lines = self.content.toPlainText().split("\n")
        lines.append(text)
        lines = lines[-50:]
        self.content.setPlainText("\n".join(lines))
        self.content.verticalScrollBar().setValue(
            self.content.verticalScrollBar().maximum()
        )

    def clear_log(self):
        self.content.clear()


class LogHandler(logging.Handler):
    def __init__(self, log_widget):
        super().__init__()
        self.log_widget = log_widget

    def emit(self, record):
        log_entry = self.format(record)
        self.log_widget.set_log(log_entry)


class StdoutRedirector:
    def __init__(self, log_widget):
        self.log_widget = log_widget

    def write(self, message):
        if message.strip():
            self.log_widget.set_log(message.strip())

    def flush(self):
        pass
