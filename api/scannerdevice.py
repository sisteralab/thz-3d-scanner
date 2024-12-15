import logging

import loader
from pyximc import *


logger = logging.getLogger(__name__)


class ScannerDevice:
    def __init__(self, x_port: str, y_port: str, z_port: str):
        self.user_unit = None
        self.steps_per_revolution = 200
        self.lead_screw_pitch = 2.5
        self.id_x = None
        self.id_y = None
        self.id_z = None
        self.lib = loader.lib
        self.x_port = f"xi-com:\\\\.\\{x_port}"
        self.y_port = f"xi-com:\\\\.\\{y_port}"
        self.z_port = f"xi-com:\\\\.\\{z_port}"

        if self.lib:
            logger.info("Command class initialized, stepper library loaded successfully.")
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

    def connect_devices(self):
        """
        Open a device with OS uri and return identifier of the device which can be used in calls.
        """
        try:
            self.id_x = self.lib.open_device(self.x_port.encode())
            if self.id_x <= 0:
                logger.info(f"Error open device X: {self.x_port}")
                exit(1)
            else:
                logger.info("X axis device id: " + repr(self.id_x))

            self.id_y = self.lib.open_device(self.y_port.encode())
            if self.id_y <= 0:
                logger.info(f"Error open device Y: {self.y_port}")
                exit(1)
            else:
                logger.info("Y axis device id: " + repr(self.id_y))

            self.id_z = self.lib.open_device(self.z_port.encode())
            if self.id_z <= 0:
                logger.info(f"Error open device Z: {self.z_port}")
                exit(1)
            else:
                logger.info("Z axis device id: " + repr(self.id_z))

        except:
            logger.info("COM ports not configured correctly, please check your settings.")
            # sys.exit()

    def set_units(self):
        """
        Choose the scale factor: conversion factor which is equal to the number of millimeters/inches per one step
        """
        user_unit = calibration_t()
        user_unit.A = 0.0125  # linear movement for one step
        user_unit.MicrostepMode = 9

        user_unit.A = 0.0125
        self.user_unit = user_unit
        logger.info(f"Scale factor set to: {user_unit.A} mm/step")

    def set_move_settings(self, device_id, speed, asel, decel):
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
            device_id, byref(mvst), byref(self.user_unit)
        )

    def emergency_stop(self):
        """
        Immediately stop all engines.
        """
        self.lib.command_stop(self.id_x)
        self.lib.command_stop(self.id_y)
        self.lib.command_stop(self.id_z)

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
        self.lib.command_zero(self.id_x)
        self.lib.command_zero(self.id_y)
        self.lib.command_zero(self.id_z)

    def set_axis_origin(self, device_id):
        """
        Sets the current position as zero for a given axis.
        """
        self.lib.command_zero(device_id)

    def get_position(self, device_id):
        """
        Obtaining information about the position of the positioner.

        This function allows you to get information about the current positioner coordinates,
        both in steps and in encoder counts, if it is set.
        Also, depending on the state of the mode parameter, information can be obtained in user units.
        :param device_id: device id.
        """
        x_pos = get_position_calb_t()
        result = self.lib.get_position_calb(
            device_id, byref(x_pos), byref(self.user_unit)
        )
        if result == Result.Ok:
            pass
        return x_pos.Position

    def wait_for_stop(self):
        """
        Waiting for the movement to complete.
        """
        stat = status_t()
        stat.MvCmdSts |= 0x80
        while (stat.MvCmdSts & MvcmdStatus.MVCMD_RUNNING) > 0:
            result1 = self.lib.get_status(self.id_x, byref(stat))
            result2 = self.lib.get_status(self.id_y, byref(stat))
            result3 = self.lib.get_status(self.id_z, byref(stat))
            if result1 == Result.Ok and result2 == Result.Ok and result3 == Result.Ok:
                self.lib.msec_sleep(10)

    def wait_for_stop_x(self):
        self.lib.command_wait_for_stop(self.id_x, 100)

    def wait_for_stop_y(self):
        self.lib.command_wait_for_stop(self.id_y, 100)

    def wait_for_stop_z(self):
        self.lib.command_wait_for_stop(self.id_z, 100)

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

    def move_axis(self, device_id, position):
        """
        Move to the specified coordinate on the x-axis.
        :param device_id: the device id.
        :param position: the position of the destination.
        """
        self.lib.command_move_calb(device_id, c_float(position), byref(self.user_unit))
        self.wait_for_stop()

    def move_x(self, position):
        """
        Move to the specified coordinate on the x-axis.
        :param position: the position of the destination.
        """
        self.lib.command_move_calb(self.id_x, c_float(position), byref(self.user_unit))
        self.wait_for_stop_x()

    def move_y(self, position):
        """
        Move to the specified coordinate on the y-axis.
        :param position: the position of the destination.
        """
        self.lib.command_move_calb(self.id_y, c_float(position), byref(self.user_unit))
        self.wait_for_stop_y()

    def move_z(self, position):
        """
        Move to the specified coordinate on the z-axis.
        :param position: the position of the destination
        """
        self.lib.command_move_calb(self.id_z, c_float(position), byref(self.user_unit))
        self.wait_for_stop_z()

    def shift_axis(self, device_id, distance):
        """
        Shift by the specified offset coordinates on the x-axis.
        :param device_id: the device id.
        :param distance: size of the offset in user units.
        """
        self.lib.command_movr_calb(device_id, c_float(distance), byref(self.user_unit))
        self.wait_for_stop()

    def shift_x(self, distance):
        """
        Shift by the specified offset coordinates on the x-axis.
        :param distance: size of the offset in user units.
        """
        self.lib.command_movr_calb(self.id_x, c_float(distance), byref(self.user_unit))
        self.wait_for_stop()

    def shift_y(self, distance):
        """
        Shift by the specified offset coordinates on the y-axis.
        :param distance: size of the offset in user units.
        """
        self.lib.command_movr_calb(self.id_y, c_float(distance), byref(self.user_unit))
        self.wait_for_stop()

    def shift_z(self, distance):
        """
        Shift by the specified offset coordinates.
        :param distance: size of the offset in user units.
        """
        self.lib.command_movr_calb(self.id_z, c_float(distance), byref(self.user_unit))
        self.wait_for_stop()

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
        self.lib.set_home_settings_calb(device_id, byref(hmst), byref(self.user_unit))

        self.lib.home_settings_calb_t(fast_home, slow_home, home_delta)

    def go_home(self):
        """
        Go home.
        """
        self.move_x(0)
        self.move_y(0)
        self.move_z(0)
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
        device_list = [self.id_x, self.id_y, self.id_z]
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
        self.lib.close_device(byref(cast(self.id_x, POINTER(c_int))))
        self.lib.close_device(byref(cast(self.id_y, POINTER(c_int))))
        self.lib.close_device(byref(cast(self.id_z, POINTER(c_int))))

    def initial_setup(self, max_linear_speed: float, acceleration: float, deceleration: float):
        """
        A coroutine for initial start.
        :return:
        """
        self.connect_devices()
        self.set_units()

        for _ in range(1, 4):
            self.set_move_settings(
                _, max_linear_speed, acceleration, deceleration
            )
        # self.go_home()
