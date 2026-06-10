from PySide6.QtCore import Qt


class SafeWheelMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        # Process wheel event only if the spinbox has focus
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
