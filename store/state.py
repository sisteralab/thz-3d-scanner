from PySide6.QtCore import QSettings
from typing import Optional

from api.scannerdevice import ScannerDevice
from api.signal_generator import SignalGenerator
from api.vna import VNABlock
from store.config import (
    VnaConfig,
    ScannerConfig,
    SignalGeneratorConfig1,
    SignalGeneratorConfig2,
)
from utils.exceptions import DeviceConnectionError


class State:
    settings = QSettings("settings.ini", QSettings.IniFormat)

    measure_running = False
    monitor_running = False
    scanner: Optional[ScannerDevice] = None
    vna: Optional[VNABlock] = None
    generator_1: Optional[SignalGenerator] = None
    generator_2: Optional[SignalGenerator] = None

    x_start: float = float(settings.value("Measure/x_start", -10))
    x_stop: float = float(settings.value("Measure/x_stop", -90))
    x_points: float = float(settings.value("Measure/x_points", 4))
    x_step: float = float(settings.value("Measure/x_step", 0))

    y_start: float = float(settings.value("Measure/y_start", -10))
    y_stop: float = float(settings.value("Measure/y_stop", -90))
    y_points: float = float(settings.value("Measure/y_points", 4))
    y_step: float = float(settings.value("Measure/y_step", 0))

    z_start: float = float(settings.value("Measure/z_start", -10))
    z_stop: float = float(settings.value("Measure/z_stop", -90))
    z_points: float = float(settings.value("Measure/z_points", 4))
    z_step: float = float(settings.value("Measure/z_step", 0))

    generator_freq_start_1: float = float(
        settings.value("Measure/generator_freq_start_1", 0)
    )
    generator_freq_stop_1: float = float(
        settings.value("Measure/generator_freq_stop_1", 0)
    )
    generator_freq_points_1: float = float(
        settings.value("Measure/generator_freq_points_1", 1)
    )

    generator_freq_start_2: float = float(
        settings.value("Measure/generator_freq_start_2", 0)
    )
    generator_freq_stop_2: float = float(
        settings.value("Measure/generator_freq_stop_2", 0)
    )
    generator_freq_points_2: float = float(
        settings.value("Measure/generator_freq_points_2", 1)
    )

    use_x_sweep: bool = settings.value("Measure/use_x_sweep", "true") == "true"
    use_y_sweep: bool = settings.value("Measure/use_y_sweep", "true") == "true"
    use_z_sweep: bool = settings.value("Measure/use_z_sweep", "true") == "true"
    use_z_snake_pattern: bool = (
        settings.value("Measure/use_z_snake_pattern", "true") == "true"
    )

    # Movement delays in milliseconds
    x_movement_delay: int = int(settings.value("Measure/x_movement_delay", 100))
    y_movement_delay: int = int(settings.value("Measure/y_movement_delay", 150))
    z_movement_delay: int = int(settings.value("Measure/z_movement_delay", 200))
    no_movement_delay: int = int(settings.value("Measure/no_movement_delay", 50))

    scanner_x_port: str = settings.value("Scanner/x_port", "COM5")
    scanner_y_port: str = settings.value("Scanner/y_port", "COM6")
    scanner_z_port: str = settings.value("Scanner/z_port", "COM7")

    @classmethod
    def store_state(cls):
        cls.settings.setValue("Measure/use_x_sweep", cls.use_x_sweep)
        cls.settings.setValue("Measure/use_y_sweep", cls.use_y_sweep)
        cls.settings.setValue("Measure/use_z_sweep", cls.use_z_sweep)
        cls.settings.setValue("Measure/use_z_snake_pattern", cls.use_z_snake_pattern)

        cls.settings.setValue("Measure/x_movement_delay", cls.x_movement_delay)
        cls.settings.setValue("Measure/y_movement_delay", cls.y_movement_delay)
        cls.settings.setValue("Measure/z_movement_delay", cls.z_movement_delay)
        cls.settings.setValue("Measure/no_movement_delay", cls.no_movement_delay)

        cls.settings.setValue("Measure/x_start", cls.x_start)
        cls.settings.setValue("Measure/x_stop", cls.x_stop)
        cls.settings.setValue("Measure/x_points", cls.x_points)
        cls.settings.setValue("Measure/x_points", cls.x_points)
        cls.settings.setValue("Measure/x_step", cls.x_step)

        cls.settings.setValue("Measure/y_start", cls.y_start)
        cls.settings.setValue("Measure/y_stop", cls.y_stop)
        cls.settings.setValue("Measure/y_points", cls.y_points)
        cls.settings.setValue("Measure/y_points", cls.y_points)
        cls.settings.setValue("Measure/y_step", cls.y_step)

        cls.settings.setValue("Measure/z_start", cls.z_start)
        cls.settings.setValue("Measure/z_stop", cls.z_stop)
        cls.settings.setValue("Measure/z_points", cls.z_points)
        cls.settings.setValue("Measure/z_points", cls.z_points)
        cls.settings.setValue("Measure/z_step", cls.z_step)

        cls.settings.setValue(
            "Measure/generator_freq_start_1", cls.generator_freq_start_1
        )
        cls.settings.setValue(
            "Measure/generator_freq_stop_1", cls.generator_freq_stop_1
        )
        cls.settings.setValue(
            "Measure/generator_freq_points_1", cls.generator_freq_points_1
        )

        cls.settings.setValue(
            "Measure/generator_freq_start_2", cls.generator_freq_start_2
        )
        cls.settings.setValue(
            "Measure/generator_freq_stop_2", cls.generator_freq_stop_2
        )
        cls.settings.setValue(
            "Measure/generator_freq_points_2", cls.generator_freq_points_2
        )

        cls.settings.sync()

    @classmethod
    def init_scanner(cls) -> bool:
        cls.del_scanner()
        cls.scanner = ScannerDevice(
            x_port=ScannerConfig.AXIS_X_PORT,
            y_port=ScannerConfig.AXIS_Y_PORT,
            z_port=ScannerConfig.AXIS_Z_PORT,
        )
        status = cls.scanner.connect_devices()
        if not status:
            cls.del_scanner()
            return False
        cls.scanner.set_units()
        return True

    @classmethod
    def init_vna(cls) -> bool:
        try:
            cls.del_vna()
            cls.vna = VNABlock(
                host=VnaConfig.HOST,
                port=VnaConfig.PORT,
            )
        except DeviceConnectionError:
            cls.vna = None
            return False

        test_result = cls.vna.test()
        if not test_result:
            cls.vna = None
            return False
        return True

    @classmethod
    def init_generator_1(cls) -> bool:
        try:
            cls.del_generator_1()
            cls.generator_1 = SignalGenerator(
                host=SignalGeneratorConfig1.HOST,
                port=SignalGeneratorConfig1.PORT,
                gpib=SignalGeneratorConfig1.GPIB,
            )
        except DeviceConnectionError:
            cls.generator_1 = None
            return False

        test_result = cls.generator_1.test()
        if not test_result:
            cls.generator_1 = None
            return False
        return True

    @classmethod
    def init_generator_2(cls) -> bool:
        try:
            cls.del_generator_2()
            cls.generator_2 = SignalGenerator(
                host=SignalGeneratorConfig2.HOST,
                port=SignalGeneratorConfig2.PORT,
                gpib=SignalGeneratorConfig2.GPIB,
            )
        except DeviceConnectionError:
            cls.generator_2 = None
            return False

        test_result = cls.generator_2.test()
        if not test_result:
            cls.generator_2 = None
            return False
        return True

    @classmethod
    def del_scanner(cls):
        if not cls.scanner:
            return
        cls.scanner.disconnect_devices()
        del cls.scanner
        cls.scanner = None

    @classmethod
    def del_vna(cls):
        if not cls.vna:
            return
        del cls.vna
        cls.vna = None

    @classmethod
    def del_generator_1(cls):
        if not cls.generator_1:
            return
        del cls.generator_1
        cls.generator_1 = None

    @classmethod
    def del_generator_2(cls):
        if not cls.generator_2:
            return
        del cls.generator_2
        cls.generator_2 = None
