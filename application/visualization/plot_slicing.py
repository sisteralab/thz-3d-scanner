from __future__ import annotations

from typing import Any

import numpy as np


PLOT_PLANE_ZX = "ZX"
PLOT_PLANE_XZ = "XZ"
PLOT_PLANE_YX = "YX"
PLOT_PLANE_XY = "XY"
PLOT_PLANE_ZY = "ZY"
PLOT_PLANE_YZ = "YZ"
PLOT_PLANE_OPTIONS = (
    (PLOT_PLANE_ZX, "Z(X)"),
    (PLOT_PLANE_XZ, "X(Z)"),
    (PLOT_PLANE_YX, "Y(X)"),
    (PLOT_PLANE_XY, "X(Y)"),
    (PLOT_PLANE_ZY, "Z(Y)"),
    (PLOT_PLANE_YZ, "Y(Z)"),
)
PLOT_PLANE_AXIS_MAP = {
    PLOT_PLANE_ZX: ("X", "Z"),
    PLOT_PLANE_XZ: ("Z", "X"),
    PLOT_PLANE_YX: ("X", "Y"),
    PLOT_PLANE_XY: ("Y", "X"),
    PLOT_PLANE_ZY: ("Y", "Z"),
    PLOT_PLANE_YZ: ("Z", "Y"),
}
SOURCE_AXIS_ORDER = ("Y", "X", "Z")
SOURCE_AXIS_INDEX = {"Y": 0, "X": 1, "Z": 2}
SOURCE_AXIS_KEY = {"Y": "y", "X": "x", "Z": "z"}
VOLUME_DATA_KEYS = {
    "amplitude",
    "phase",
    "complex_real",
    "complex_imag",
    "calibrated_amplitude",
    "calibrated_phase",
    "calibrated_complex_real",
    "calibrated_complex_imag",
    "z_request",
    "z_response",
    "vna_latency_ms",
    "late_sample",
}


def plot_plane_axes(plane: str) -> tuple[str, str]:
    return PLOT_PLANE_AXIS_MAP.get(plane, PLOT_PLANE_AXIS_MAP[PLOT_PLANE_ZX])


def plot_slice_axis_name(plane: str) -> str:
    horizontal_axis, vertical_axis = plot_plane_axes(plane)
    for axis_name in SOURCE_AXIS_ORDER:
        if axis_name not in (horizontal_axis, vertical_axis):
            return axis_name
    return "Y"


def axis_values(data: dict[str, Any], axis_name: str, expected_size: int) -> np.ndarray:
    values = np.asarray(data.get(axis_name, np.arange(expected_size)), dtype=float)
    if values.size != expected_size:
        values = np.arange(expected_size, dtype=float)
    return values


def extract_plot_axis_values(data: Any, axis_name: str) -> np.ndarray:
    if not isinstance(data, dict):
        return np.array([0.0], dtype=float)

    amplitude = np.asarray(data.get("amplitude", []))
    if amplitude.ndim != 3:
        return np.array([0.0], dtype=float)

    axis_name = str(axis_name).upper()
    expected_size = amplitude.shape[SOURCE_AXIS_INDEX.get(axis_name, 0)]
    axis_key = SOURCE_AXIS_KEY.get(axis_name, "y")
    return axis_values(data, axis_key, expected_size)


def extract_axis_slice(
    data: Any,
    plane: str = PLOT_PLANE_ZX,
    slice_index: int = 0,
) -> dict[str, Any]:
    """Return a 2D slice view with shape [horizontal_axis, vertical_axis]."""
    if not isinstance(data, dict):
        return {}

    amplitude = np.asarray(data.get("amplitude", []))
    if amplitude.ndim != 3:
        return data

    axis_sizes = {
        "Y": amplitude.shape[0],
        "X": amplitude.shape[1],
        "Z": amplitude.shape[2],
    }
    if any(size == 0 for size in axis_sizes.values()):
        return data

    sliced = {key: value for key, value in data.items() if key not in VOLUME_DATA_KEYS}
    source_axis_values = {
        axis_name: axis_values(
            data,
            SOURCE_AXIS_KEY[axis_name],
            axis_sizes[axis_name],
        )
        for axis_name in SOURCE_AXIS_ORDER
    }
    horizontal_axis_name, vertical_axis_name = plot_plane_axes(plane)
    slice_axis = plot_slice_axis_name(plane)
    slice_values = source_axis_values[slice_axis]
    slice_idx = int(np.clip(slice_index, 0, slice_values.size - 1))
    horizontal_values = source_axis_values[horizontal_axis_name]
    vertical_values = source_axis_values[vertical_axis_name]
    remaining_axis_order = [
        axis_name for axis_name in SOURCE_AXIS_ORDER if axis_name != slice_axis
    ]

    def slice_array(arr: np.ndarray) -> np.ndarray:
        indexer = [slice(None)] * arr.ndim
        indexer[SOURCE_AXIS_INDEX[slice_axis]] = slice_idx
        cut = arr[tuple(indexer)]
        transpose_axes = (
            remaining_axis_order.index(horizontal_axis_name),
            remaining_axis_order.index(vertical_axis_name),
        )
        if transpose_axes == (0, 1):
            return cut
        return np.transpose(cut, transpose_axes)

    for key in VOLUME_DATA_KEYS:
        arr = np.asarray(data.get(key, []))
        if arr.ndim == 3 and arr.shape == amplitude.shape:
            sliced[key] = slice_array(arr)

    sliced["x"] = horizontal_values
    sliced["z"] = vertical_values
    sliced["plot_plane"] = plane
    sliced["horizontal_axis_name"] = horizontal_axis_name
    sliced["vertical_axis_name"] = vertical_axis_name
    sliced["slice_axis_name"] = slice_axis
    sliced["slice_index"] = slice_idx
    sliced["slice_value"] = float(slice_values[slice_idx])
    return sliced


def extract_xz_slice(data: Any, y_index: int) -> dict[str, Any]:
    return extract_axis_slice(data, PLOT_PLANE_ZX, y_index)
