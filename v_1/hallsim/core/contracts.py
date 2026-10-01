"""Общие типы данных для программы."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .enums import (
    ColorRangeMode,
    FieldNormalization,
    FieldStatus,
    SensorOrientationMode,
)


@dataclass(frozen=True)
class MagnetDefinition:
    """Прототип: момент задаётся явно, а не выводится из названия материала."""

    id: str
    display_name: str
    moment_Am2: float
    material: str | None = None
    grade: str | None = None
    reference_dimensions_mm: tuple[float, float, float] | None = None
    source_note: str | None = None
    is_builtin: bool = True


@dataclass
class MagnetState:
    """Положение магнита; angle_deg задаёт направление S -> N."""

    id: int
    enabled: bool
    x_mm: float
    y_mm: float
    angle_deg: float
    definition_id: str


@dataclass
class SensorState:
    """angle_deg — положительная чувствительная ось, не угол пластины."""

    x_mm: float
    y_mm: float
    angle_deg: float
    orientation_mode: SensorOrientationMode


@dataclass
class PathState:
    """Отрезок A-B; samples — число точек, включая оба конца."""

    enabled: bool
    ax_mm: float
    ay_mm: float
    bx_mm: float
    by_mm: float
    samples: int = 300


@dataclass
class ViewSettings:
    show_heatmap: bool = True
    show_field_lines: bool = True
    show_grid: bool = False
    normalization: FieldNormalization = FieldNormalization.POWER
    color_range_mode: ColorRangeMode = ColorRangeMode.AUTO_PERCENTILE
    color_min_mT: float | None = None
    color_max_mT: float | None = None
    percentile_clip: float = 99.5
    power_gamma: float = 0.5


@dataclass
class SceneState:
    magnets: list[MagnetState]
    sensor: SensorState
    path: PathState
    view: ViewSettings
    revision: int = 0


@dataclass
class AppSettings:
    theme: str = "light"
    last_zoom: float = 1.0
    save_last_scene: bool = True
    last_scene: SceneState | None = None


@dataclass(frozen=True)
class FieldPoint:
    """Поле в точке; направление неопределено при ZERO_FIELD/сингулярности."""

    bx_mT: float
    by_mT: float
    modB_mT: float
    direction_deg: float | None
    status: FieldStatus


@dataclass(frozen=True)
class FieldGrid:
    """Оси имеют формы (nx,), (ny,); поля и маска — (ny, nx).

    Строка соответствует Y, столбец — X. Невалидные элементы полей — NaN.
    frozen запрещает замену атрибутов, но не изменение элементов массивов.
    """

    x_mm: NDArray[np.float64]
    y_mm: NDArray[np.float64]
    bx_mT: NDArray[np.float64]
    by_mT: NDArray[np.float64]
    modB_mT: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    scene_revision: int


@dataclass(frozen=True)
class SensorReading:
    """Знаковое показание в мТл и исходное поле в положении датчика."""

    value_mT: float
    field: FieldPoint


@dataclass(frozen=True)
class PathProfile:
    """Три массива формы (samples,); расстояние отсчитывается от A."""

    distance_mm: NDArray[np.float64]
    modB_mT: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    scene_revision: int
