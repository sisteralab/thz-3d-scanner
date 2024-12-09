class State:
	UNITS = "mm"  # mm/in
	CURRENT_MOTION_MODE = None
	POSITIONING_MODE = None
	WORKING_PLANE = None
	MONITORING = False
	X_TEMP = 0
	Y_TEMP = 0
	Z_TEMP = 0
	X_CURR = 1
	Y_CURR = 1
	Z_CURR = 1
	TIMER_TIMEOUT = 0.1


class Config:
	# COM ports
	COM_OK = False
	AXIS_X_PORT: str = 'COM32'
	AXIS_Y_PORT: str = 'COM33'
	AXIS_Z_PORT: str = 'COM4'
	if AXIS_X_PORT != AXIS_Y_PORT != AXIS_Z_PORT:
		COM_OK = True

	# Movement settings in millimeters per second
	MAX_LINEAR_SPEED: int = 40
	ACCELERATION: int = 20
	DECELERATION: int = 20
	SAFE_X = 0
	SAFE_Y = 0
	SAFE_Z = 0


class Feedback:
	PRINT_LINES = False
	PRINT_ACTION = False
	COORDINATES = {
		'x': 0,
		'y': 0,
		'z': 0
	}
