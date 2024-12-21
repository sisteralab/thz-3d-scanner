from typing_extensions import Optional

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
    measure_running = False
    monitor_running = False
    scanner: Optional[ScannerDevice] = None
    vna: Optional[VNABlock] = None
    generator_1: Optional[SignalGenerator] = None
    generator_2: Optional[SignalGenerator] = None

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
