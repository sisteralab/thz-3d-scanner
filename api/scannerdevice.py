import logging
import time

import loader
from pyximc import *


logger = logging.getLogger(__name__)


class ScannerDevice:
    def __init__(
        self,
        x_port: str,
        y_port: str,
        z_port: str,
        rotation_port: str = "",
        x_distance_per_step: float = 0.0125,
        y_distance_per_step: float = 0.0125,
        z_distance_per_step: float = 0.0125,
        rotation_degrees_per_step: float = 0.01,
    ):
        self.user_unit = None
        self.x_unit = None
        self.y_unit = None
        self.z_unit = None
        self.rotation_unit = None
        self.steps_per_revolution = 200
        self.lead_screw_pitch = 2.5
        self.id_x = None
        self.id_y = None
        self.id_z = None
        self.id_rotation = None
        self.lib = loader.lib
        self.x_port = f"xi-com:\\\\.\\{x_port}" if x_port.strip() else ""
        self.y_port = f"xi-com:\\\\.\\{y_port}" if y_port.strip() else ""
        self.z_port = f"xi-com:\\\\.\\{z_port}" if z_port.strip() else ""
        self.rotation_port = (
            f"xi-com:\\\\.\\{rotation_port}" if rotation_port.strip() else ""
        )
        self.x_distance_per_step = float(x_distance_per_step)
        self.y_distance_per_step = float(y_distance_per_step)
        self.z_distance_per_step = float(z_distance_per_step)
        self.rotation_degrees_per_step = float(rotation_degrees_per_step)

        if self.lib:
            logger.info(
                "Command class initialized, stepper library loaded successfully."
            )
        else:
            logger.error("Unable find ximc library")

    def test_info(self, device_id):
        """
        Reading information about the device.
        :param device_id: device id.
        """
        logger.info("\nGet device info")
        x_device_information = device_information_t()
        result = self.lib.get_device_information(device_id, byref(x_device_information))
        logger.info("Result: " + repr(result))
        if result == Result.Ok:
            logger.info("Device information:")
            logger.info(
                " Manufacturer: "
                + repr(string_at(x_device_information.Manufacturer).decode())
            )
            logger.info(
                " ManufacturerId: "
                + repr(string_at(x_device_information.ManufacturerId).decode())
            )
            logger.info(
                " ProductDescription: "
                + repr(string_at(x_device_information.ProductDescription).decode())
            )
            logger.info(
                " Hardware version: "
                + repr(x_device_information.Major)
                + "."
                + repr(x_device_information.Minor)
                + "."
                + repr(x_device_information.Release)
            )

    def test_serial(self, device_id):
        """
        Reading the device's serial number.
        :param device_id: device id.
        """
        x_serial = c_uint()
        result = self.lib.get_serial_number(device_id, byref(x_serial))
        if result == Result.Ok:
            logger.info(" Serial: " + repr(x_serial.value))

    def _connect_device(self, port: str, axis_name: str):
        if not port:
            logger.info(f"{axis_name} axis port is empty; skipping.")
            return None

        device_id = self.lib.open_device(port.encode())
        if device_id <= 0:
            logger.error(f"Error open device {axis_name}: {port}")
            return None

        logger.info(f"{axis_name} axis device id: {device_id!r}")
        return device_id

    def connected_axes(self):
        axes = []
        for axis, device_id in (
            ("X", self.id_x),
            ("Y", self.id_y),
            ("Z", self.id_z),
            ("Rotation", self.id_rotation),
        ):
            if device_id:
                axes.append(axis)
        return axes

    def has_connected_devices(self) -> bool:
        return bool(self.connected_axes())

    def _iter_device_ids(self):
        return tuple(
            device_id
            for device_id in (self.id_x, self.id_y, self.id_z, self.id_rotation)
            if device_id
        )

    @staticmethod
    def _require_device(device_id, axis_name: str):
        if not device_id:
            raise RuntimeError(f"{axis_name} axis is not initialized")

    @staticmethod
    def _result_name(result):
        for name in ("Ok", "Error", "NotImplemented", "ValueError", "NoDevice"):
            if getattr(Result, name, None) == result:
                return name
        return str(result)

    def _raise_result_error(self, message, result):
        raise RuntimeError(f"{message}: {self._result_name(result)} ({result})")

    def connect_devices(self) -> bool:
        """
        Open a device with OS uri and return identifier of the device which can be used in calls.
        """
        try:
            self.id_x = self._connect_device(self.x_port, "X")
            self.id_y = self._connect_device(self.y_port, "Y")
            self.id_z = self._connect_device(self.z_port, "Z")

            self.id_rotation = self._connect_device(self.rotation_port, "Rotation")

        except Exception as e:
            logger.exception(
                "COM ports not configured correctly, please check your settings.",
                exc_info=True,
            )
        return self.has_connected_devices()

    def _command_move_calb_checked(
        self,
        axis_name: str,
        position,
        calibration,
        async_move: bool = False,
        timeout_s: float = 300.0,
    ):
        device_id = getattr(self, f"id_{axis_name.lower()}", None)
        self._require_device(device_id, axis_name)
        result = self.lib.command_move_calb(
            device_id, c_float(position), byref(calibration)
        )
        if result != Result.Ok:
            self._raise_result_error(f"Failed to move {axis_name} axis", result)
        if not async_move:
            self.wait_for_stop_device(device_id, timeout_s=timeout_s)

    def set_units(self):
        """
        Choose the scale factor: conversion factor which is equal to the number of millimeters/inches per one step
        """
        self.x_unit = self._create_calibration(self.x_distance_per_step)
        self.y_unit = self._create_calibration(self.y_distance_per_step)
        self.z_unit = self._create_calibration(self.z_distance_per_step)
        self.user_unit = self.x_unit
        logger.info(f"X scale factor set to: {self.x_unit.A} mm/step")
        logger.info(f"Y scale factor set to: {self.y_unit.A} mm/step")
        logger.info(f"Z scale factor set to: {self.z_unit.A} mm/step")

        self.rotation_unit = self._create_calibration(self.rotation_degrees_per_step)
        logger.info(f"Rotation scale factor set to: {self.rotation_unit.A} deg/step")

    @staticmethod
    def _create_calibration(scale):
        unit = calibration_t()
        unit.A = float(scale)
        unit.MicrostepMode = 9
        return unit

    def _get_device_calibration(self, device_id):
        if device_id == self.id_x:
            return self.x_unit
        if device_id == self.id_y:
            return self.y_unit
        if device_id == self.id_z:
            return self.z_unit
        if device_id == self.id_rotation:
            return self.rotation_unit
        return self.user_unit

    def _get_calibration(self, calibration=None):
        return calibration if calibration is not None else self.user_unit

    def _resolve_calibration(self, device_id, calibration=None):
        return (
            calibration
            if calibration is not None
            else self._get_device_calibration(device_id)
        )

    def set_move_settings(self, device_id, speed, asel, decel, calibration=None):
        """
        Setting up movement parameters.
        :param device_id: device id.
        :param speed: Target speed.
        :param asel: Motor shaft acceleration, steps/s^2.
        :param decel: Motor shaft deceleration, steps/s^2.
        """
        # Create move settings structure
        mvst = move_settings_calb_t()

        # Filling in the structure move_settings_t
        mvst.Speed = float(speed)
        mvst.Accel = float(asel)
        mvst.Decel = float(decel)

        # Writing data to the controller
        result = self.lib.set_move_settings_calb(
            device_id,
            byref(mvst),
            byref(self._resolve_calibration(device_id, calibration)),
        )
        return result == Result.Ok

    def get_move_settings(self, device_id, calibration=None):
        """
        Read calibrated move profile for given axis.
        :param device_id: device id.
        :return: dict with speed/accel/decel or None if unavailable.
        """
        fn = getattr(self.lib, "get_move_settings_calb", None)
        if fn is None:
            return None

        mvst = move_settings_calb_t()
        result = fn(
            device_id,
            byref(mvst),
            byref(self._resolve_calibration(device_id, calibration)),
        )
        if result != Result.Ok:
            return None

        return {
            "speed": float(mvst.Speed),
            "accel": float(mvst.Accel),
            "decel": float(mvst.Decel),
        }

    def emergency_stop(self):
        """
        Immediately stop all engines.
        """
        for device_id in self._iter_device_ids():
            self.lib.command_stop(device_id)

    def soft_stop(self, device_id):
        """
        Stop selected axis using the controller deceleration profile.
        """
        self._require_device(device_id, "Selected")
        result = self.lib.command_sstp(device_id)
        if result != Result.Ok:
            self._raise_result_error("Failed to soft-stop axis", result)

    def soft_stop_all(self):
        """
        Stop all connected axes using their configured deceleration profiles.
        """
        for device_id in self._iter_device_ids():
            try:
                self.soft_stop(device_id)
            except Exception:
                logger.exception("Failed to soft-stop axis")

    def dwell(self, duration):
        """
        Sleeps for a specified amount of time.
        :param duration: time in milliseconds
        :return:
        """
        self.lib.msec_sleep(duration)

    def set_origin(self):
        """
        Sets the current position as zero for all axes.
        """
        for device_id in self._iter_device_ids():
            self.lib.command_zero(device_id)

    def set_axis_origin(self, device_id):
        """
        Sets the current position as zero for a given axis.
        """
        self._require_device(device_id, "Selected")
        self.lib.command_zero(device_id)

    def get_position(self, device_id, calibration=None):
        """
        Obtaining information about the position of the positioner.

        This function allows you to get information about the current positioner coordinates,
        both in steps and in encoder counts, if it is set.
        Also, depending on the state of the mode parameter, information can be obtained in user units.
        :param device_id: device id.
        """
        self._require_device(device_id, "Selected")
        x_pos = get_position_calb_t()
        result = self.lib.get_position_calb(
            device_id,
            byref(x_pos),
            byref(self._resolve_calibration(device_id, calibration)),
        )
        if result == Result.Ok:
            pass
        return x_pos.Position

    def wait_for_stop(self):
        """
        Waiting for the movement to complete.
        """
        for device_id in self._iter_device_ids():
            self.wait_for_stop_device(device_id)

    def is_moving(self, device_id) -> bool:
        self._require_device(device_id, "Selected")
        stat = status_t()
        result = self.lib.get_status(device_id, byref(stat))
        if result != Result.Ok:
            raise RuntimeError(f"Failed to read axis status: {result}")
        return bool(stat.MvCmdSts & MvcmdStatus.MVCMD_RUNNING)

    def wait_for_stop_device(
        self,
        device_id,
        timeout_s: float = 300.0,
        poll_ms: int = 50,
        stop_on_timeout: bool = True,
    ):
        self._require_device(device_id, "Selected")
        started = time.monotonic()
        start_grace_s = 0.05
        saw_running = False
        poll_s = max(0.001, float(poll_ms) / 1000.0)
        while True:
            moving = self.is_moving(device_id)
            saw_running = saw_running or moving
            if not moving and (
                saw_running or time.monotonic() - started >= start_grace_s
            ):
                return True
            if timeout_s is not None and time.monotonic() - started > float(timeout_s):
                if stop_on_timeout:
                    try:
                        self.stop(device_id)
                    except Exception:
                        logger.exception("Failed to stop timed out axis")
                raise TimeoutError(f"Axis {device_id} did not stop within {timeout_s}s")
            time.sleep(poll_s)

    def wait_for_stop_x(self, timeout_s: float = 300.0):
        self._require_device(self.id_x, "X")
        self.wait_for_stop_device(self.id_x, timeout_s=timeout_s)

    def wait_for_stop_y(self, timeout_s: float = 300.0):
        self._require_device(self.id_y, "Y")
        self.wait_for_stop_device(self.id_y, timeout_s=timeout_s)

    def wait_for_stop_z(self, timeout_s: float = 300.0):
        self._require_device(self.id_z, "Z")
        self.wait_for_stop_device(self.id_z, timeout_s=timeout_s)

    def wait_for_stop_rotation(self, timeout_s: float = 300.0):
        self._require_device(self.id_rotation, "Rotation")
        self.wait_for_stop_device(self.id_rotation, timeout_s=timeout_s)

    def move_left(self, device_id):
        """
        Move to the left.
        :param device_id: device id.
        """
        self.lib.command_left(device_id)

    def move_right(self, device_id):
        """
        Move to the right.
        :param device_id: device id.
        """
        self.lib.command_right(device_id)

    def move_axis(self, device_id, position, calibration=None):
        """
        Move to the specified coordinate on the x-axis.
        :param device_id: the device id.
        :param position: the position of the destination.
        """
        self._require_device(device_id, "Selected")
        result = self.lib.command_move_calb(
            device_id,
            c_float(position),
            byref(self._resolve_calibration(device_id, calibration)),
        )
        if result != Result.Ok:
            raise RuntimeError(f"Failed to move axis {device_id}: {result}")
        self.wait_for_stop()

    def move_x(self, position):
        """
        Move to the specified coordinate on the x-axis.
        :param position: the position of the destination.
        """
        self._require_device(self.id_x, "X")
        self._command_move_calb_checked("X", position, self.x_unit)

    def move_y(self, position):
        """
        Move to the specified coordinate on the y-axis.
        :param position: the position of the destination.
        """
        self._require_device(self.id_y, "Y")
        self._command_move_calb_checked("Y", position, self.y_unit)

    def move_z(self, position):
        """
        Move to the specified coordinate on the z-axis.
        :param position: the position of the destination
        """
        self._require_device(self.id_z, "Z")
        self._command_move_calb_checked("Z", position, self.z_unit)

    def move_z_async(self, position):
        """
        Start movement to the specified Z coordinate without waiting for completion.
        :param position: destination position in user units.
        """
        self._require_device(self.id_z, "Z")
        self._command_move_calb_checked("Z", position, self.z_unit, async_move=True)

    def move_rotation(self, position, timeout_s: float = 300.0):
        """
        Move rotation axis to the specified angle in degrees.
        :param position: destination angle in degrees.
        """
        self._require_device(self.id_rotation, "Rotation")
        self._command_move_calb_checked(
            "Rotation", position, self.rotation_unit, timeout_s=timeout_s
        )

    def move_rotation_async(self, position):
        """
        Start movement to the specified rotation angle without waiting for completion.
        :param position: destination angle in degrees.
        """
        self._require_device(self.id_rotation, "Rotation")
        self._command_move_calb_checked(
            "Rotation", position, self.rotation_unit, async_move=True
        )

    def shift_axis(self, device_id, distance, calibration=None):
        """
        Shift by the specified offset coordinates on the x-axis.
        :param device_id: the device id.
        :param distance: size of the offset in user units.
        """
        self._require_device(device_id, "Selected")
        self.lib.command_movr_calb(
            device_id,
            c_float(distance),
            byref(self._resolve_calibration(device_id, calibration)),
        )
        self.wait_for_stop()

    def shift_x(self, distance):
        """
        Shift by the specified offset coordinates on the x-axis.
        :param distance: size of the offset in user units.
        """
        self._require_device(self.id_x, "X")
        self.lib.command_movr_calb(self.id_x, c_float(distance), byref(self.x_unit))
        self.wait_for_stop()

    def shift_y(self, distance):
        """
        Shift by the specified offset coordinates on the y-axis.
        :param distance: size of the offset in user units.
        """
        self._require_device(self.id_y, "Y")
        self.lib.command_movr_calb(self.id_y, c_float(distance), byref(self.y_unit))
        self.wait_for_stop()

    def shift_z(self, distance):
        """
        Shift by the specified offset coordinates.
        :param distance: size of the offset in user units.
        """
        self._require_device(self.id_z, "Z")
        self.lib.command_movr_calb(self.id_z, c_float(distance), byref(self.z_unit))
        self.wait_for_stop()

    def shift_rotation(self, distance):
        """
        Shift rotation axis by the specified angle in degrees.
        :param distance: angle offset in degrees.
        """
        self._require_device(self.id_rotation, "Rotation")
        self.lib.command_movr_calb(
            self.id_rotation, c_float(distance), byref(self.rotation_unit)
        )
        self.wait_for_stop_rotation()

    def set_home_settings(self, device_id, fast_home, slow_home, home_delta):
        """
        Position calibration settings which use user units.
        :param fast_home: speed used for first motion.
        :param slow_home: speed used for second motion.
        :param home_delta: distance from break point.
        """
        # Create move settings structure
        hmst = home_settings_calb_t()

        # Filling in the structure move_settings_t
        hmst.FastHome = float(fast_home)
        hmst.SlowHome = float(slow_home)
        hmst.HomeDelta = float(home_delta)

        # Writing data to the controller
        self.lib.set_home_settings_calb(
            device_id, byref(hmst), byref(self._get_device_calibration(device_id))
        )

        self.lib.home_settings_calb_t(fast_home, slow_home, home_delta)

    def go_home(self):
        """
        Go home.
        """
        if self.id_x:
            self.move_x(0)
        if self.id_y:
            self.move_y(0)
        if self.id_z:
            self.move_z(0)
        if self.id_rotation:
            self.move_rotation(0)
        self.wait_for_stop()

    def set_axis_limits(self, device_id, min_value, max_value):
        """
        Set limits for given axis.
        :param device_id:
        :param min_value:
        :param max_value:
        :return:
        """
        edgst = edges_settings_t()
        edgst.LeftBorder = int(
            min_value * self.steps_per_revolution / self.lead_screw_pitch
        )
        edgst.RightBorder = int(
            max_value * self.steps_per_revolution / self.lead_screw_pitch
        )
        edgst.BorderFlags = 7
        # edgst.EnderFlags = 1

        result = self.lib.set_edges_settings(device_id, byref(edgst))

        if result == Result.Ok:
            logger.info(f"Limits set for axis {device_id}")

    def unset_axis_limits(self, device_id):
        edgst = edges_settings_t()

        edgst.BorderFlags = 6
        # edgst.EnderFlags = 1

        result = self.lib.set_edges_settings(device_id, byref(edgst))
        if result == Result.Ok:
            logger.info(f"Limits set for axis {device_id}")

    def get_axis_limits(self):
        device_list = self._iter_device_ids()
        settings = []
        edges_settings_t()
        for item in device_list:
            edgst = edges_settings_t()
            self.lib.get_edges_settings(item, byref(edgst))
            settings.append(edgst.LeftBorder)
            settings.append(edgst.RightBorder)

        return settings

    def flex_wait_for_stop(self, device_id, msec=10, mode=1):
        """
        This function performs dynamic output coordinate in the process of moving.

        :param lib: structure for accessing the functionality of the libximc library.
        :param device_id: device id.
        :param msec: Pause between reading the coordinates.
        :param mode: data mode in feedback counts or in user units. (Default value = 1)
        """

        stat = status_t()
        stat.MvCmdSts |= 0x80
        while stat.MvCmdSts & MvcmdStatus.MVCMD_RUNNING > 0:
            result = self.lib.get_status(device_id, byref(stat))
            if result == Result.Ok:
                self.lib.msec_sleep(msec)

    def stop(self, device_id):
        self.lib.command_stop(device_id)

    def set_homezero(self, device_id):
        """
        Make home command, wait until it is finished and make zero command.
        """
        self.lib.command_homezero(device_id)

    def disconnect_devices(self):
        """
        Close devices.
        """
        for device_id in (self.id_x, self.id_y, self.id_z, self.id_rotation):
            if device_id:
                self.lib.close_device(byref(cast(device_id, POINTER(c_int))))

    def initial_setup(
        self, max_linear_speed: float, acceleration: float, deceleration: float
    ):
        """
        A coroutine for initial start.
        :return:
        """
        self.connect_devices()
        self.set_units()

        for _ in range(1, 4):
            self.set_move_settings(_, max_linear_speed, acceleration, deceleration)
        # self.go_home()
