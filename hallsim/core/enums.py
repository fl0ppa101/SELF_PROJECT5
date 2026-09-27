"""Перечисляемые типы для взаимодействия модулей. Подробнее: ARCHITECTURE.MD, раздел 11"""

from enum import Enum, auto


class FieldStatus(Enum):
    """Состояние расчёта в точке; ZERO_FIELD не означает ошибку."""

    OK = auto()
    INSIDE_SINGULARITY = auto()
    ZERO_FIELD = auto()
    INVALID_INPUT = auto()


class SensorOrientationMode(Enum):
    AUTO = auto()
    MANUAL = auto()


class FieldNormalization(Enum):
    LINEAR = auto()
    LOG = auto()
    POWER = auto()


class ColorRangeMode(Enum):
    AUTO_PERCENTILE = auto()
    AUTO_FULL = auto()
    MANUAL = auto()
