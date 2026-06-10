from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from application.measurement.config import MeasurementConfig


@dataclass(frozen=True)
class MeasurementPlan:
    freq_points: int
    vna_cw_points: int
    base_steps_per_angle: int
    calibration_steps_per_angle: int
    rotation_points: int
    total_steps: int


@dataclass(frozen=True)
class AxisMotionProfile:
    speed: float
    accel: float
    decel: float


@dataclass(frozen=True)
class MotionProfiles:
    x: AxisMotionProfile
    y: AxisMotionProfile
    z: AxisMotionProfile
    rotation: AxisMotionProfile


def build_measurement_plan(config: MeasurementConfig) -> MeasurementPlan:
    freq_points = (
        int(np.min([config.generator_1.freq_points, config.generator_2.freq_points]))
        if config.use_generators
        else 1
    )
    vna_cw_points = (
        max(1, int(config.vna.cw_frequency_points))
        if config.vna.cw_frequency_enabled
        else 1
    )
    base_steps_per_angle = (
        int(config.y_range.size) * int(config.x_range.size) * int(config.z_range.size)
    )
    full_z_lines = int(config.y_range.size) * int(config.x_range.size)
    calibration_steps_per_angle = 0
    if config.center_calibration.enabled and config.center_calibration.period_lines > 0:
        calibration_steps_per_angle = 1 + int(
            np.ceil(full_z_lines / config.center_calibration.period_lines)
        )
    rotation_points = int(config.rotation_range.size)
    total_steps = (
        rotation_points
        * (base_steps_per_angle + calibration_steps_per_angle)
        * freq_points
        * vna_cw_points
    )
    return MeasurementPlan(
        freq_points=freq_points,
        vna_cw_points=vna_cw_points,
        base_steps_per_angle=base_steps_per_angle,
        calibration_steps_per_angle=calibration_steps_per_angle,
        rotation_points=rotation_points,
        total_steps=total_steps,
    )


def estimate_motion_time_s(
    distance: float,
    profile: AxisMotionProfile,
) -> float:
    distance = abs(float(distance))
    speed = abs(float(profile.speed))
    accel = abs(float(profile.accel))
    decel = abs(float(profile.decel))
    if distance <= 0.0 or speed <= 0.0:
        return 0.0
    if accel <= 0.0 or decel <= 0.0:
        return distance / speed

    accel_distance = speed * speed / (2.0 * accel)
    decel_distance = speed * speed / (2.0 * decel)
    if distance >= accel_distance + decel_distance:
        cruise_distance = distance - accel_distance - decel_distance
        return speed / accel + cruise_distance / speed + speed / decel

    peak_speed = np.sqrt(2.0 * distance * accel * decel / (accel + decel))
    return float(peak_speed / accel + peak_speed / decel)


def estimate_measurement_seconds(
    config: MeasurementConfig,
    motion: MotionProfiles,
) -> float:
    plan = build_measurement_plan(config)
    multiplier = plan.freq_points * plan.vna_cw_points

    per_angle_s = (
        _axis_loop_time_s(
            config.y_range,
            motion.y,
            _ms_to_s(config.movement.y_delay_ms),
            config.sweep.use_y,
        )
        + _repeated_axis_loop_time_s(
            config.x_range,
            int(config.y_range.size),
            motion.x,
            _ms_to_s(config.movement.x_delay_ms),
            config.sweep.use_x,
        )
        + _z_scan_time_per_angle_s(config, motion)
        + _calibration_time_per_angle_s(
            config, motion, plan.calibration_steps_per_angle
        )
    )

    rotation_s = _rotation_time_per_frequency_block_s(config, motion)
    generator_setup_s = (
        0.3 * plan.freq_points * plan.vna_cw_points if config.use_generators else 0.0
    )
    setup_s = generator_setup_s + _vna_cw_setup_time_s(config)
    return max(
        0.0, multiplier * (rotation_s + plan.rotation_points * per_angle_s) + setup_s
    )


def estimate_vna_sample_time_s(config: MeasurementConfig) -> float:
    sweep_time = max(0.0, float(config.vna.stop_time) - float(config.vna.start_time))
    if config.vna.average_enabled:
        sweep_time *= max(1, int(config.vna.average_count))
    return sweep_time


def _ms_to_s(value: int | float) -> float:
    return max(0.0, float(value) / 1000.0)


def _axis_loop_time_s(
    values: np.ndarray,
    profile: AxisMotionProfile,
    delay_s: float,
    enabled: bool,
) -> float:
    if not enabled:
        return 0.0
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return 0.0
    motion_s = estimate_motion_time_s(values[0], profile)
    if values.size > 1:
        motion_s += _path_time_s(np.diff(values), profile)
    return motion_s + delay_s * int(values.size)


def _repeated_axis_loop_time_s(
    values: np.ndarray,
    repetitions: int,
    profile: AxisMotionProfile,
    delay_s: float,
    enabled: bool,
) -> float:
    if not enabled or repetitions <= 0:
        return 0.0
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return 0.0

    first_motion_s = estimate_motion_time_s(values[0], profile)
    internal_motion_s = _path_time_s(np.diff(values), profile)
    reset_motion_s = (
        estimate_motion_time_s(values[-1] - values[0], profile)
        if values.size > 1
        else 0.0
    )
    repeated_motion_s = first_motion_s + internal_motion_s
    if repetitions > 1:
        repeated_motion_s += (repetitions - 1) * (reset_motion_s + internal_motion_s)
    return repeated_motion_s + delay_s * int(values.size) * int(repetitions)


def _path_time_s(deltas: np.ndarray, profile: AxisMotionProfile) -> float:
    if deltas.size == 0:
        return 0.0
    return float(sum(estimate_motion_time_s(delta, profile) for delta in deltas))


def _z_scan_time_per_angle_s(
    config: MeasurementConfig,
    motion: MotionProfiles,
) -> float:
    line_count = int(config.y_range.size) * int(config.x_range.size)
    if line_count <= 0:
        return 0.0
    z_count = int(config.z_range.size)
    sample_s = estimate_vna_sample_time_s(config)

    if config.sweep.use_z_fly_mode and config.sweep.use_z:
        return _z_fly_time_per_angle_s(config, motion, line_count, sample_s)

    point_count = line_count * z_count
    if not config.sweep.use_z:
        return point_count * (_ms_to_s(config.movement.no_movement_delay_ms) + sample_s)

    delay_s = _ms_to_s(config.movement.z_delay_ms)
    z_values = np.asarray(config.z_range, dtype=float)
    first_line_motion_s = estimate_motion_time_s(z_values[0], motion.z)
    internal_motion_s = _path_time_s(np.diff(z_values), motion.z)
    line_delay_s = delay_s * z_count

    if z_count <= 1:
        motion_s = first_line_motion_s
    elif config.sweep.use_z_snake_pattern:
        motion_s = first_line_motion_s + internal_motion_s * line_count
    else:
        reset_motion_s = estimate_motion_time_s(z_values[-1] - z_values[0], motion.z)
        motion_s = first_line_motion_s + internal_motion_s
        if line_count > 1:
            motion_s += (line_count - 1) * (reset_motion_s + internal_motion_s)

    return motion_s + line_delay_s * line_count + sample_s * point_count


def _z_fly_time_per_angle_s(
    config: MeasurementConfig,
    motion: MotionProfiles,
    line_count: int,
    sample_s: float,
) -> float:
    z_values = np.asarray(config.z_range, dtype=float)
    z_count = int(z_values.size)
    if z_count <= 1:
        return line_count * (
            _ms_to_s(config.movement.z_delay_ms)
            + estimate_motion_time_s(z_values[0] if z_count else 0.0, motion.z)
            + sample_s
        )

    start_z = float(z_values[0])
    end_z = float(z_values[-1])
    reset_motion_s = estimate_motion_time_s(end_z - start_z, motion.z)
    first_move_s = estimate_motion_time_s(start_z, motion.z)
    fly_speed = _effective_z_fly_speed(config, sample_s)
    fly_motion_s = abs(end_z - start_z) / max(fly_speed, 1e-6)
    acquisition_s = sample_s + max(fly_motion_s, (z_count - 1) * sample_s)
    probe_s = sample_s if config.sweep.auto_adjust_z_fly_speed else 0.0
    delay_s = _ms_to_s(config.movement.z_delay_ms)

    total = first_move_s + delay_s + probe_s + acquisition_s
    if line_count > 1:
        total += (line_count - 1) * (reset_motion_s + delay_s + probe_s + acquisition_s)
    return total


def _effective_z_fly_speed(config: MeasurementConfig, sample_s: float) -> float:
    requested_speed = max(1e-6, abs(float(config.sweep.z_fly_speed)))
    if not config.sweep.auto_adjust_z_fly_speed:
        return requested_speed

    z_values = np.asarray(config.z_range, dtype=float)
    dz = np.diff(z_values)
    if dz.size == 0:
        return requested_speed

    min_step = float(np.min(np.abs(dz)))
    if min_step <= 0.0:
        return requested_speed

    poll_s = max(0.001, _ms_to_s(config.movement.fly_poll_delay_ms))
    tolerance = max(0.05, 0.45 * min_step)
    latency_s = max(sample_s, 0.001)
    sample_budget_s = latency_s + poll_s + 0.02
    safe_by_sample = 0.8 * min_step / sample_budget_s
    safe_by_poll = 0.8 * (2.0 * tolerance) / poll_s
    return max(1e-6, min(requested_speed, safe_by_sample, safe_by_poll))


def _rotation_time_per_frequency_block_s(
    config: MeasurementConfig,
    motion: MotionProfiles,
) -> float:
    return _axis_loop_time_s(
        config.rotation_range,
        motion.rotation,
        _ms_to_s(config.movement.no_movement_delay_ms),
        config.sweep.use_rotation,
    )


def _vna_cw_setup_time_s(config: MeasurementConfig) -> float:
    if not config.vna.cw_frequency_enabled:
        return 0.0
    return 0.1 * max(1, int(config.vna.cw_frequency_points))


def _calibration_time_per_angle_s(
    config: MeasurementConfig,
    motion: MotionProfiles,
    calibration_count: int,
) -> float:
    if calibration_count <= 0:
        return 0.0

    one_way_s = (
        _calibration_axis_time_s(
            config.x_range,
            config.center_calibration.x,
            motion.x,
            _ms_to_s(config.movement.x_delay_ms),
            config.sweep.use_x,
        )
        + _calibration_axis_time_s(
            config.y_range,
            config.center_calibration.y,
            motion.y,
            _ms_to_s(config.movement.y_delay_ms),
            config.sweep.use_y,
        )
        + _calibration_axis_time_s(
            config.z_range,
            config.center_calibration.z,
            motion.z,
            _ms_to_s(config.movement.z_delay_ms),
            config.sweep.use_z,
        )
    )
    sample_s = estimate_vna_sample_time_s(config)
    initial_s = one_way_s + sample_s
    restore_xy_s = _calibration_restore_axis_time_s(
        config.x_range,
        config.center_calibration.x,
        motion.x,
        _ms_to_s(config.movement.x_delay_ms),
        config.sweep.use_x,
    ) + _calibration_restore_axis_time_s(
        config.y_range,
        config.center_calibration.y,
        motion.y,
        _ms_to_s(config.movement.y_delay_ms),
        config.sweep.use_y,
    )
    return initial_s + max(0, calibration_count - 1) * (
        one_way_s + sample_s + restore_xy_s
    )


def _calibration_axis_time_s(
    scan_values: np.ndarray,
    center: float,
    profile: AxisMotionProfile,
    delay_s: float,
    enabled: bool,
) -> float:
    if not enabled:
        return 0.0
    max_distance = _max_distance_to_center(scan_values, center)
    return estimate_motion_time_s(max_distance, profile) + delay_s


def _calibration_restore_axis_time_s(
    scan_values: np.ndarray,
    center: float,
    profile: AxisMotionProfile,
    delay_s: float,
    enabled: bool,
) -> float:
    if not enabled:
        return 0.0
    max_distance = _max_distance_to_center(scan_values, center)
    return estimate_motion_time_s(max_distance, profile) + delay_s


def _max_distance_to_center(scan_values: np.ndarray, center: float) -> float:
    values = np.asarray(scan_values, dtype=float)
    if values.size == 0:
        return abs(float(center))
    return float(np.max(np.abs(values - float(center))))


def normalize_amplitudes(
    amplitudes: list[float] | tuple[float, ...],
    freq_points: int,
) -> list[float | None]:
    values = list(amplitudes)
    if len(values) >= freq_points:
        return values[:freq_points]
    if values:
        return values + [values[-1] for _ in range(freq_points - len(values))]
    return [None for _ in range(freq_points)]
