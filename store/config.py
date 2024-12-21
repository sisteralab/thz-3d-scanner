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


class SignalGeneratorConfig1:
    id: int = 1
    HOST: str = "169.254.156.103"
    PORT: int = 1234
    GPIB: int = 19


class SignalGeneratorConfig2:
    id: int = 2
    HOST: str = "169.254.156.103"
    PORT: int = 1234
    GPIB: int = 18


class InterfaceOpenConfig:
    StartX: int = 10
    StopX: int = -10
    PointsX: int = 20
    StepX: int = 1

    StartY: int = 10
    StopY: int = -10
    PointsY: int = 20
    StepY: int = 1

    StartZ: int = 10
    StopZ: int = -10
    PointsZ: int = 20
    StepZ: int = 1
