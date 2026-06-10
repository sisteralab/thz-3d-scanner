from __future__ import annotations

from typing import Protocol


class VnaPort(Protocol):
    def set_parameter(self, value: str) -> None:
        ...

    def set_start_time(self, value: float) -> None:
        ...

    def set_stop_time(self, value: float) -> None:
        ...

    def set_sweep(self, points: int) -> None:
        ...

    def set_power(self, value: float) -> None:
        ...

    def set_cw_frequency(self, value: float) -> None:
        ...

    def set_output_state(self, enabled: bool) -> None:
        ...

    def set_channel_format(self, value: str) -> None:
        ...

    def set_average_count(self, value: int) -> None:
        ...

    def set_average_status(self, enabled: bool) -> None:
        ...

    def set_bandwidth(self, value: int) -> None:
        ...

    def get_data(self) -> tuple[list[float], list[float]]:
        ...


class SignalGeneratorPort(Protocol):
    def set_frequency(self, value_hz: float) -> None:
        ...

    def set_power(self, value_dbm: float) -> None:
        ...


class ScannerPort(Protocol):
    id_x: int | None
    id_y: int | None
    id_z: int | None
    id_rotation: int | None
    x_unit: object
    y_unit: object
    z_unit: object
    rotation_unit: object

    def get_position(self, axis_id: int, unit: object | None = None) -> float:
        ...

    def get_move_settings(self, axis_id: int) -> dict[str, float]:
        ...

    def set_move_settings(
        self,
        axis_id: int,
        speed: float,
        accel: float,
        decel: float,
    ) -> None:
        ...

    def move_x(self, value: float) -> None:
        ...

    def move_y(self, value: float) -> None:
        ...

    def move_z(self, value: float) -> None:
        ...

    def move_z_async(self, value: float) -> None:
        ...

    def move_rotation(self, value: float, timeout_s: float | None = None) -> None:
        ...

    def soft_stop(self, axis_id: int) -> None:
        ...

    def soft_stop_all(self) -> None:
        ...

    def wait_for_stop_z(self, timeout_s: float) -> None:
        ...


class MeasurementRuntimePort(Protocol):
    scanner: ScannerPort
    vna: VnaPort
    generator_1: SignalGeneratorPort
    generator_2: SignalGeneratorPort
    scanner_z_speed: float
    scanner_z_accel: float
    scanner_z_decel: float

    def is_measure_running(self) -> bool:
        ...

    def plot_update_hz(self, fallback: float) -> float:
        ...
