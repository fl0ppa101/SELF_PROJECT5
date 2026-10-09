"""Hall effect in SI; public values are mA, mm, mT and mV."""

import math
import numpy as np
from hallsim.core.contracts import HallReading, HallSensorParameters, SensorStudyCurve
from hallsim.core.enums import SensorStudyAxis
from .sensor import project_field
from .validation import finite_real, positive_real


def validate_parameters(params, *, reconstruction=False):
    if not isinstance(params, HallSensorParameters):
        raise ValueError("Expected HallSensorParameters")
    current = finite_real(params.current_mA, "current_mA")
    thickness = positive_real(params.thickness_mm, "thickness_mm")
    coefficient = finite_real(params.hall_coefficient_m3_C, "hall_coefficient_m3_C")
    if reconstruction and (current == 0 or coefficient == 0):
        raise ValueError("Для восстановления поля нужны ненулевые I и R_H")
    return current, thickness, coefficient


def voltage_mV(component_mT, current_mA, thickness_mm, coefficient):
    return (
        coefficient
        * (np.asarray(current_mA) * 1e-3)
        * (np.asarray(component_mT) * 1e-3)
        / (np.asarray(thickness_mm) * 1e-3)
        * 1e3
    )


def compute_hall_from_field(field, sensor_angle_deg, params):
    current, thickness, coefficient = validate_parameters(params)
    angle = finite_real(sensor_angle_deg, "sensor_angle_deg") % 360
    component = project_field(field, angle)
    value = float(voltage_mV(component, current, thickness, coefficient))
    return HallReading(field, angle, component, value)


def reconstruct_modB_from_hall_voltage(max_abs_hall_voltage_mV, params):
    current, thickness, coefficient = validate_parameters(params, reconstruction=True)
    voltage = finite_real(max_abs_hall_voltage_mV, "max_abs_hall_voltage_mV")
    if voltage < 0:
        raise ValueError("Максимальное абсолютное напряжение должно быть >= 0")
    result = (
        (thickness * 1e-3) * (voltage * 1e-3) / abs(coefficient * current * 1e-3) * 1e3
    )
    if not math.isfinite(result):
        raise ValueError("Параметры приводят к переполнению")
    return result


def compute_sensor_study_curve(field, params, sensor_angle_deg, axis, x_values):
    current, thickness, coefficient = validate_parameters(params)
    x = np.array(x_values, dtype=float, copy=True)
    if x.ndim != 1 or not x.size or not np.isfinite(x).all():
        raise ValueError("Ожидается непустой конечный одномерный массив")
    component = project_field(field, sensor_angle_deg)
    if axis is SensorStudyAxis.CURRENT:
        y, unit = voltage_mV(component, x, thickness, coefficient), "мА"
    elif axis is SensorStudyAxis.THICKNESS:
        if np.any(x <= 0):
            raise ValueError("Толщина должна быть положительной")
        y, unit = voltage_mV(component, current, x, coefficient), "мм"
    elif axis is SensorStudyAxis.ANGLE:
        radians = np.deg2rad(x)
        values = field.bx_mT * np.cos(radians) + field.by_mT * np.sin(radians)
        y, unit = voltage_mV(values, current, thickness, coefficient), "°"
    else:
        raise ValueError("Неизвестная ось исследования")
    return SensorStudyCurve(axis, x, np.array(y, dtype=float, copy=True), unit)
