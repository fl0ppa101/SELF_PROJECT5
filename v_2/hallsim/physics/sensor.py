"""Проекция поля и направление чувствительной оси датчика."""

import math
from numbers import Real

from hallsim.core.contracts import (
    FieldPoint,
    MagnetDefinition,
    MagnetState,
    SensorReading,
    SensorState,
)
from hallsim.core.enums import FieldStatus

from .field import compute_field_at, direction_from_components
from .validation import validate_sensor


def project_field(field: FieldPoint, angle_deg: float) -> float:
    """Знаковая проекция в мТл; угол в градусах. Недопустимое поле даёт NaN."""
    if isinstance(angle_deg, bool) or not isinstance(angle_deg, Real):
        raise ValueError("angle_deg must be a real number")
    if not math.isfinite(angle_deg):
        raise ValueError("angle_deg must be finite")

    if not isinstance(field, FieldPoint):
        raise ValueError("field must be a FieldPoint")
    if not isinstance(field.status, FieldStatus):
        raise ValueError("field.status must be a FieldStatus")

    # У недопустимого поля компоненты могут быть NaN по контракту.
    if field.status in (FieldStatus.INSIDE_SINGULARITY, FieldStatus.INVALID_INPUT):
        return math.nan

    for name, value in (("bx_mT", field.bx_mT), ("by_mT", field.by_mT)):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{name} must be a real number")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite")

    angle_rad = math.radians(angle_deg)
    projection = field.bx_mT * math.cos(angle_rad) + field.by_mT * math.sin(angle_rad)

    return projection


def optimal_angle(field: FieldPoint) -> float | None:
    """Угол по Bx/By для показания +|B| в градусах [0, 360), либо None."""
    if not isinstance(field, FieldPoint):
        raise ValueError("field must be a FieldPoint")
    if not isinstance(field.status, FieldStatus):
        raise ValueError("field.status must be a FieldStatus")

    if field.status in (
        FieldStatus.ZERO_FIELD,
        FieldStatus.INSIDE_SINGULARITY,
        FieldStatus.INVALID_INPUT,
    ):
        return None

    for name, value in (("bx_mT", field.bx_mT), ("by_mT", field.by_mT)):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{name} must be a real number for OK status")
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite for OK status")

    return direction_from_components(field.bx_mT, field.by_mT)


def compute_sensor_reading(
    magnets: list[MagnetState],
    magnet_catalog: dict[str, MagnetDefinition],
    sensor: SensorState,
    *,
    singularity_radius_mm: float,
    zero_field_epsilon_mT: float,
) -> SensorReading:
    """Показание для sensor.angle_deg; выравнивание AUTO выполняет приложение."""
    validate_sensor(sensor)
    field = compute_field_at(
        magnets,
        magnet_catalog,
        sensor.x_mm,
        sensor.y_mm,
        singularity_radius_mm=singularity_radius_mm,
        zero_field_epsilon_mT=zero_field_epsilon_mT,
    )
    return SensorReading(value_mT=project_field(field, sensor.angle_deg), field=field)


def compute_optimal_sensor_angle(
    magnets: list[MagnetState],
    magnet_catalog: dict[str, MagnetDefinition],
    x_mm: float,
    y_mm: float,
    *,
    singularity_radius_mm: float,
    zero_field_epsilon_mT: float,
) -> float | None:
    field = compute_field_at(
        magnets,
        magnet_catalog,
        x_mm,
        y_mm,
        singularity_radius_mm=singularity_radius_mm,
        zero_field_epsilon_mT=zero_field_epsilon_mT,
    )
    return optimal_angle(field)
