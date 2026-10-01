"""Shared contract: verbatim fields from 00_ARCHITECTURE_v2.md."""
from enum import Enum, auto

class FieldStatus(Enum):
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
