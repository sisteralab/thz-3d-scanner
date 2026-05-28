import logging

from PySide6 import QtWidgets


class LogWidget(QtWidgets.QGroupBox):
    MAX_LINES = 1000

    def __init__(self, parent):
        super().__init__(parent)
        self.setTitle("Log")
        self.setMaximumHeight(220)
        self.setMinimumWidth(400)
        self._paused_lines = []

        layout = QtWidgets.QHBoxLayout()
        controls_layout = QtWidgets.QVBoxLayout()

        self.content = QtWidgets.QPlainTextEdit(self)
        self.content.setReadOnly(True)
        self.content.setMaximumBlockCount(self.MAX_LINES)
        self.content.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )

        self.btn_pause = QtWidgets.QPushButton("Pause", self)
        self.btn_pause.setCheckable(True)
        self.btn_pause.toggled.connect(self.toggle_pause)

        self.auto_scroll_checkbox = QtWidgets.QCheckBox("Auto-scroll", self)
        self.auto_scroll_checkbox.setChecked(True)

        self.btn_clear = QtWidgets.QPushButton("Clear", self)
        self.btn_clear.clicked.connect(self.clear_log)

        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.auto_scroll_checkbox)
        controls_layout.addWidget(self.btn_clear)
        controls_layout.addStretch(1)

        layout.addWidget(self.content)
        layout.addLayout(controls_layout)
        self.setLayout(layout)

    def set_log(self, text: str):
        if self.btn_pause.isChecked():
            self._paused_lines.append(text)
            self._paused_lines = self._paused_lines[-self.MAX_LINES :]
            return

        self._append_log(text, scroll_to_bottom=self.auto_scroll_checkbox.isChecked())

    def toggle_pause(self, paused: bool):
        self.btn_pause.setText("Resume" if paused else "Pause")
        if paused or not self._paused_lines:
            return

        should_scroll = self.auto_scroll_checkbox.isChecked()
        for line in self._paused_lines:
            self._append_log(line, scroll_to_bottom=False)
        self._paused_lines.clear()

        if should_scroll:
            self.content.verticalScrollBar().setValue(
                self.content.verticalScrollBar().maximum()
            )

    def clear_log(self):
        self.content.clear()
        self._paused_lines.clear()

    def _append_log(self, text: str, scroll_to_bottom: bool):
        scroll_bar = self.content.verticalScrollBar()
        previous_value = scroll_bar.value()

        self.content.appendPlainText(text)

        if scroll_to_bottom:
            scroll_bar.setValue(scroll_bar.maximum())
        else:
            scroll_bar.setValue(previous_value)


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
