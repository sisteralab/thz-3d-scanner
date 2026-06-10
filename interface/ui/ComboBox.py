from PySide6.QtWidgets import QComboBox

from interface.ui.safe_wheel import SafeWheelMixin


class ComboBox(SafeWheelMixin, QComboBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
