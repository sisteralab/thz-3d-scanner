import logging
import time
from typing import Dict
from typing_extensions import Literal

import numpy as np

from api.adapters.socket_adapter import SocketAdapter
from utils.classes import BaseInstrument

logger = logging.getLogger(__name__)


VNA_PARAMETERS = Literal["AB", "BA"]
VNA_SWEEP_TYPES = Literal["LIN", "LOG", "SEG", "POW", "CW"]
VNA_CHANNEL_FORMATS = Literal["COMP"]


class VNABlock(BaseInstrument):
    """
    Default host 169.254.106.189
    Default port 5025
    """

    def __init__(
        self,
        host: str = "169.254.106.189",
        port: int = 5025,
    ):
        self.adapter = SocketAdapter(host=host, port=port, delay=0.1)

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

    def set_sweep_type(self, sweep_type: VNA_SWEEP_TYPES = "CW"):
        self.write(f"SWE:TYPE {sweep_type}")

    def get_sweep_type(self) -> str:
        return self.query("SWE:TYPE?")

    def set_sweep(self, points: int = 1000) -> None:
        self.write(f"SWE:POIN {points}")

    def get_sweep(self) -> int:
        return int(self.query(f"SWE:POIN?", delay=0.05))

    def set_cw_frequency(self, frequency: float):
        self.write(f"SOUR:FREQ:CW {frequency} Hz")

    def get_cw_frequency(self) -> float:
        return float(self.query(f"SOUR:FREQ:CW?"))

    def set_average_status(self, value: bool, channel: int = 1) -> None:
        status = "ON" if value else "OFF"
        self.write(f"SENSe{channel}:AVERage {status}")

    def set_average_count(self, value: int, channel: int = 1) -> None:
        self.write(f"SENSe{channel}:AVERage:COUNt {value}")

    def set_channel_format(self, form: VNA_CHANNEL_FORMATS = "COMP") -> None:
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

    def set_start_time(self, stime: float) -> None:
        ...

    def set_stop_time(self, stime: float) -> None:
        ...

    def set_parameter(
        self, parameter: VNA_PARAMETERS = "BA", trace: str = "Trc1", channel: int = 1
    ) -> None:
        self.write(f"CALCulate{channel}:PARameter:DEFine {trace},{parameter}")
        # self.write("DISP:WIND2:STAT ON")
        # self.write(f"DISP:WIND2:TRAC1:FEED Trc1")

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
        Method to get data from VNA
        """
        attempts = 5
        attempt = 0
        while attempt < attempts:
            attempt += 1
            response = self.query("CALC:DATA? FDAT").split(",")
            try:
                resp = [float(i) for i in response]
            except ValueError:
                logger.error(f"[{self.__class__.__name__}.get_data] Value error!")
                time.sleep(0.05)
                continue
            if np.sum(np.abs(resp)) > 0:
                real = resp[::2]
                imag = resp[1::2]

                return {
                    "real": real,
                    "imag": imag,
                    "amplitude": list(20 * np.log10(np.abs([r + i * 1j for r, i in zip(real, imag)]))),
                    # "frequency": self.get_cw_frequency(),
                    # "parameter": param,
                    # "power": power,
                }
        return {}


if __name__ == "__main__":
    vna = VNABlock()
    # vna.set_parameter("BA")
    # vna.set_sweep_type("CW")
    # vna.set_parameter
    vna.set_parameter("BA")
    vna.set_sweep_type("CW")
    vna.set_channel_format("COMP")
    vna.set_cw_frequency(3.067e9)
    print(vna.get_parameter_catalog())
    print(vna.get_channel_format())
    print(vna.get_cw_frequency())
    print(vna.get_data())
