from typing_extensions import Optional

from api.scannerdevice import ScannerDevice
from api.vna import VNABlock
from store.config import VnaConfig, ScannerConfig
from utils.exceptions import DeviceConnectionError


class State:
    measure_running = False
    monitor_running = False
    scanner: Optional[ScannerDevice] = None
    vna: Optional[VNABlock] = None

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
