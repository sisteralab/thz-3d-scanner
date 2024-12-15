from api.scannerdevice import ScannerDevice
from api.vna import VNABlock
from store.config import VnaConfig, ScannerConfig


class State:
    measure_running = False
    monitor_running = False
    scanner: ScannerDevice = None
    vna: VNABlock = None

    @classmethod
    def init_scanner(cls):
        cls.scanner = ScannerDevice(x_port=ScannerConfig.AXIS_X_PORT, y_port=ScannerConfig.AXIS_Y_PORT, z_port=ScannerConfig.AXIS_Z_PORT)
        cls.scanner.connect_devices()
        cls.scanner.set_units()

    @classmethod
    def init_vna(cls):
        cls.vna = VNABlock(
            host=VnaConfig.HOST,
            port=VnaConfig.PORT,
        )

    @classmethod
    def del_d3(cls):
        cls.scanner.disconnect_devices()
        del cls.scanner

    @classmethod
    def del_vna(cls):
        del cls.vna
