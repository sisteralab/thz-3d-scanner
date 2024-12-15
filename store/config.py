class ScannerConfig:
    # COM ports
    AXIS_X_PORT: str = "COM32"
    AXIS_Y_PORT: str = "COM33"
    AXIS_Z_PORT: str = "COM4"

    # Movement settings in millimeters per second
    MAX_LINEAR_SPEED: int = 40
    ACCELERATION: int = 20
    DECELERATION: int = 20
    SAFE_X = 0
    SAFE_Y = 0
    SAFE_Z = 0


class VnaConfig:
    HOST: str = "169.254.106.189"
    PORT: int = 5025
