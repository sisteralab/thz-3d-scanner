import logging
import time
from typing import Dict, Union
import socket

import numpy as np


logger = logging.getLogger(__name__)


class DeviceConnectionError(Exception):
    ...


class InstrumentAdapterInterface:
    """
    This is the base interface for Instrument adapter
    """

    def _send(self, *args, **kwargs):
        raise NotImplementedError

    def _recv(self, *args, **kwargs):
        raise NotImplementedError

    def read(self, *args, **kwargs):
        raise NotImplementedError

    def query(self, *args, **kwargs):
        raise NotImplementedError

    def write(self, *args, **kwargs):
        raise NotImplementedError

    def connect(self, *args, **kwargs):
        raise NotImplementedError

    def close(self, *args, **kwargs):
        raise NotImplementedError


class SocketAdapter(InstrumentAdapterInterface):
    def __init__(
        self,
        host: str,
        port: int,
        timeout: float = 2,
        delay: float = 0.4,
    ):
        self.socket = None
        self.host = host
        self.port = int(port)
        self.timeout = 0
        self.delay = delay
        self.init(timeout)

    def init(self, timeout: float = 2):
        if self.socket is None:
            logger.info(f"[{self.__class__.__name__}.init]Socket is None, creating ...")
            self.socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP
            )
        else:
            logger.info(
                f"[{self.__class__.__name__}.init]Socket is already existed, connecting ..."
            )
        self.connect(timeout)

    def connect(self, timeout: float = 2):
        self.set_timeout(timeout)
        try:
            self.socket.connect((self.host, self.port))
            logger.info(
                f"[{self.__class__.__name__}.connect]Socket has been connected {self.socket}."
            )
        except (OSError, TimeoutError) as e:
            logger.error(f"[{self.__class__.__name__}.connect] Error: {e}")
            raise DeviceConnectionError("Unable to connect socket")

    def is_socket_closed(self) -> Union[bool, None]:
        try:
            # this will try to read bytes without blocking and also without removing them from buffer (peek only)
            data = self.socket.recv(16)
            if len(data) == 0:
                logger.info(
                    f"[{self.__class__.__name__}.is_socket_closed] Socket is closed"
                )
                return True
        except BlockingIOError:
            logger.info(
                f"[{self.__class__.__name__}.is_socket_closed] BlockingIOError, socket is opened"
            )
            return False  # socket is open and reading from it would block
        except ConnectionResetError:
            logger.info(
                f"[{self.__class__.__name__}.is_socket_closed] ConnectionResetError, socket is closed"
            )
            return True  # socket was closed for some other reason
        except Exception as e:
            logger.error(
                f"[{self.__class__.__name__}.is_socket_closed] Unexpected exception '{e}', socket status is undefined"
            )
            return None
        logger.info(f"[{self.__class__.__name__}.is_socket_closed] Socket is opened")
        return False

    def close(self):
        if self.socket is None:
            logger.warning(f"[{self.__class__.__name__}.close] Socket is None")
            return
        self.socket.close()
        logger.info(f"[{self.__class__.__name__}.close] Socket has been closed.")

    def write(self, cmd: str, **kwargs):
        self._send(cmd)

    def read(self, num_bytes=1024, **kwargs):
        return self._recv(num_bytes)

    def query(self, cmd: str, buffer_size=1024 * 1024, delay: float = 0, **kwargs):
        self.write(cmd, **kwargs)
        if delay:
            time.sleep(delay)
        elif self.delay:
            time.sleep(self.delay)
        return self.read(num_bytes=buffer_size)

    def set_timeout(self, timeout):
        if timeout < 1e-3 or timeout > 3:
            raise ValueError("Timeout must be >= 1e-3 (1ms) and <= 3 (3s)")

        self.timeout = timeout
        self.socket.settimeout(self.timeout)

    def _send(self, value):
        encoded_value = ("%s\n" % value).encode("ascii")
        self.socket.sendall(encoded_value)

    def _recv(self, byte_num):
        value = self.socket.recv(byte_num)
        return value.decode("ascii").rstrip()

    def __del__(self):
        self.close()


class VNABlock:
    """
    Default host 169.254.106.189
    Default port 5025
    """

    def __init__(
        self,
        host: str = "169.254.106.189",
        port: int = 5025,
    ):
        self.adapter = SocketAdapter(host=host, port=port)

    def query(self, cmd: str, **kwargs) -> str:
        return self.adapter.query(cmd, **kwargs)

    def write(self, cmd: str) -> None:
        return self.adapter.write(cmd)

    def idn(self) -> str:
        return self.query("*IDN?")

    def test(self) -> bool:
        """
        Methods for self testing Instrument.
        Error - 1
        Ok - 0
        """
        result = self.idn()
        return "Rohde&Schwarz,ZVA67-4Port" in result

    def set_sweep(self, points: int = 1000) -> None:
        self.write(f"SWE:POIN {points}")

    def get_sweep(self) -> int:
        return int(self.query(f"SWE:POIN?", delay=0.05))

    def set_average_status(self, value: bool, channel: int = 1) -> None:
        status = "ON" if value else "OFF"
        self.write(f"SENSe{channel}:AVERage {status}")

    def set_average_count(self, value: int, channel: int = 1) -> None:
        self.write(f"SENSe{channel}:AVERage:COUNt {value}")

    def set_channel_format(self, form: str = "COMP") -> None:
        self.write(f"CALC:FORM {form}")

    def get_channel_format(self):
        return self.query("CALC:FORM?", delay=0.05)

    def set_power(self, power: float = -30) -> None:
        self.write(f"SOUR:POW {power}")

    def get_power(self):
        return self.query("SOUR:POW?", delay=0.05)

    def get_start_frequency(self) -> float:
        return float(self.query("SENS:FREQ:STAR?", delay=0.05))

    def get_stop_frequency(self) -> float:
        return float(self.query("SENS:FREQ:STOP?", delay=0.05))

    def set_start_frequency(self, freq: float) -> None:
        self.write(f"SENS:FREQ:STAR {freq}")

    def set_stop_frequency(self, freq: float) -> None:
        self.write(f"SENS:FREQ:STOP {freq}")

    def set_parameter(
        self, parameter: str = "S11", trace: str = "Trc1", channel: int = 1
    ) -> None:
        self.write(f"CALCulate{channel}:PARameter:DEFine {trace},{parameter}")

    def get_parameter_catalog(self, channel: int = 1) -> Dict[str, str]:
        """Current catalog of parameters
        :returns
        Dict of Trace and Parameter map {"Trc1": "S11"}
        """
        response = self.query(f"CALCulate{channel}:PARameter:CATalog?", delay=0.05)
        response = response.replace("'", "")
        lst = response.split(",")
        lst_traces = [_ for _ in lst[::2]]
        lst_params = [_ for _ in lst[1::2]]
        return dict(zip(lst_traces, lst_params))

    def get_data(self) -> Dict:
        """
        Method to get reflection level from VNA
        """
        attempts = 5
        attempt = 0
        while attempt < attempts:
            time.sleep(0.05)
            attempt += 1
            response = self.query("CALC:DATA? FDAT").split(",")
            try:
                resp = [float(i) for i in response]
            except ValueError:
                logger.error(f"[{self.__class__.__name__}.get_data] Value error!")
                continue
            if np.sum(np.abs(resp)) > 0:
                real = resp[::2]
                imag = resp[1::2]
                freq = list(
                    np.linspace(
                        self.get_start_frequency(),
                        self.get_stop_frequency(),
                        self.get_sweep(),
                    )
                )
                s_param = self.get_parameter_catalog()["Trc1"]
                power = self.get_power()

                return {
                    "array": np.array([r + i * 1j for r, i in zip(real, imag)]),
                    "real": real,
                    "imag": imag,
                    "freq": freq,
                    "parameter": s_param,
                    "power": power,
                }
        return {}
