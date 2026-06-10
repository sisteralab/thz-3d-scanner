from PySide6.QtWidgets import QSpinBox

from interface.ui.safe_wheel import SafeWheelMixin


class SpinBox(SafeWheelMixin, QSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
