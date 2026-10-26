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


class AppSection(Enum):
    VISUALIZATION = auto()
    EXPERIMENT = auto()
    SENSOR_STUDY = auto()


class VisualizationPreset(Enum):
    ILLUSTRATIVE = auto()
    LINEAR = auto()
    CUSTOM = auto()


class MeasurementSource(Enum):
    MANUAL = auto()
    AUTOMATIC = auto()


class SensorStudyAxis(Enum):
    CURRENT = auto()
    THICKNESS = auto()
    ANGLE = auto()


class ExperimentPointStatus(Enum):
    PENDING = auto()
    ACTIVE = auto()
    COMPLETED = auto()
    INVALID = auto()
