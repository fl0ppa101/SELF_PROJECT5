"""Общие типы данных для программы."""

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .enums import (
    ColorRangeMode,
    FieldNormalization,
    FieldStatus,
    SensorOrientationMode,
    AppSection,
    VisualizationPreset,
    MeasurementSource,
    SensorStudyAxis,
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
    percentile_clip: float = 99.0
    power_gamma: float = 0.4
    preset: VisualizationPreset = VisualizationPreset.ILLUSTRATIVE
    palette: str = "hall"
    line_density: float = 1.0


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
    last_section: AppSection = AppSection.VISUALIZATION


@dataclass(frozen=True)
class HallSensorParameters:
    current_mA: float
    thickness_mm: float
    hall_coefficient_m3_C: float


@dataclass(frozen=True)
class HallReading:
    field: "FieldPoint"
    sensor_angle_deg: float
    sensitive_component_mT: float
    hall_voltage_mV: float


@dataclass
class ExperimentPathState:
    enabled: bool
    ax_mm: float
    ay_mm: float
    bx_mm: float
    by_mm: float


@dataclass
class ExperimentConfig:
    automatic_point_count: int = 50
    angular_step_deg: float = 10.0


@dataclass(frozen=True)
class ExperimentPointResult:
    s_mm: float
    x_mm: float
    y_mm: float
    source: MeasurementSource
    measurement_count: int
    max_abs_hall_voltage_mV: float
    measured_modB_mT: float


@dataclass
class ExperimentState:
    path: ExperimentPathState
    config: ExperimentConfig
    sensor_params: HallSensorParameters
    points: list[ExperimentPointResult] = field(default_factory=list)
    locked: bool = False


@dataclass(frozen=True)
class AngularScanResult:
    x_mm: float
    y_mm: float
    angles_deg: NDArray[np.float64]
    hall_voltage_mV: NDArray[np.float64]
    max_abs_hall_voltage_mV: float
    measured_modB_mT: float
    field: "FieldPoint"


@dataclass(frozen=True)
class ExperimentComparison:
    measured_distance_mm: NDArray[np.float64]
    measured_modB_mT: NDArray[np.float64]
    theoretical_at_measured_mT: NDArray[np.float64]
    abs_error_mT: NDArray[np.float64]
    mean_abs_error_mT: float
    theory_profile: "PathProfile"


@dataclass
class SensorStudyState:
    sensor_params: HallSensorParameters
    selected_axis: SensorStudyAxis = SensorStudyAxis.CURRENT


@dataclass(frozen=True)
class SensorStudyCurve:
    axis: SensorStudyAxis
    x_values: NDArray[np.float64]
    hall_voltage_mV: NDArray[np.float64]
    x_unit: str


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
