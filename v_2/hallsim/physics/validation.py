"""Проверки входных данных Physics API; ошибки вызывают ValueError."""

import math
from numbers import Integral, Real

from hallsim.core.contracts import MagnetDefinition, MagnetState, SensorState
from hallsim.core.enums import SensorOrientationMode


def finite_real(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a real number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(f"{name} must be finite") from error
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def positive_real(value: object, name: str) -> float:
    result = finite_real(value, name)
    if result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def sample_count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 2:
        raise ValueError(f"{name} must be an integer >= 2")
    return int(value)


def copy_catalog(catalog: dict[str, MagnetDefinition]) -> dict[str, MagnetDefinition]:
    if not isinstance(catalog, dict):
        raise ValueError("magnet_catalog must be a dictionary")
    for key, definition in catalog.items():
        if not isinstance(definition, MagnetDefinition):
            raise ValueError("catalog entries must be MagnetDefinition objects")
        if not isinstance(key, str) or key != definition.id:
            raise ValueError("catalog keys must match MagnetDefinition.id")
        positive_real(definition.moment_Am2, "moment_Am2")
    return dict(catalog)


def validate_magnets(
    magnets: list[MagnetState],
    catalog: dict[str, MagnetDefinition],
) -> None:
    if not isinstance(magnets, list):
        raise ValueError("magnets must be a list")
    for magnet in magnets:
        if not isinstance(magnet, MagnetState):
            raise ValueError("magnets must contain MagnetState objects")
        if not isinstance(magnet.enabled, bool):
            raise ValueError("magnet.enabled must be bool")
        if not magnet.enabled:
            continue
        finite_real(magnet.x_mm, "magnet.x_mm")
        finite_real(magnet.y_mm, "magnet.y_mm")
        finite_real(magnet.angle_deg, "magnet.angle_deg")
        if (
            not isinstance(magnet.definition_id, str)
            or magnet.definition_id not in catalog
        ):
            raise ValueError("magnet.definition_id must exist in magnet_catalog")
        definition = catalog[magnet.definition_id]
        if not isinstance(definition, MagnetDefinition):
            raise ValueError("catalog entries must be MagnetDefinition objects")
        positive_real(definition.moment_Am2, "moment_Am2")


def validate_sensor(sensor: SensorState) -> None:
    if not isinstance(sensor, SensorState):
        raise ValueError("sensor must be a SensorState")
    finite_real(sensor.x_mm, "sensor.x_mm")
    finite_real(sensor.y_mm, "sensor.y_mm")
    finite_real(sensor.angle_deg, "sensor.angle_deg")
    if not isinstance(sensor.orientation_mode, SensorOrientationMode):
        raise ValueError("sensor.orientation_mode must be a SensorOrientationMode")
