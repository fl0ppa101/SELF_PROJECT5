from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .enums import ColorRangeMode, FieldNormalization, FieldStatus, SensorOrientationMode


@dataclass(frozen=True)
class MagnetDefinition:
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
    id: int
    enabled: bool
    x_mm: float
    y_mm: float
    angle_deg: float
    definition_id: str


@dataclass
class SensorState:
    x_mm: float
    y_mm: float
    angle_deg: float
    orientation_mode: SensorOrientationMode


@dataclass
class PathState:
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
    view: ViewSettings = field(default_factory=ViewSettings)
    revision: int = 0


@dataclass
class AppSettings:
    theme: str = "light"
    last_zoom: float = 1.0
    save_last_scene: bool = True
    last_scene: SceneState | None = None


@dataclass(frozen=True)
class FieldPoint:
    bx_mT: float
    by_mT: float
    modB_mT: float
    direction_deg: float | None
    status: FieldStatus


@dataclass(frozen=True)
class FieldGrid:
    x_mm: NDArray[np.float64]
    y_mm: NDArray[np.float64]
    bx_mT: NDArray[np.float64]
    by_mT: NDArray[np.float64]
    modB_mT: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    scene_revision: int


@dataclass(frozen=True)
class SensorReading:
    value_mT: float
    field: FieldPoint


@dataclass(frozen=True)
class PathProfile:
    distance_mm: NDArray[np.float64]
    modB_mT: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    scene_revision: int

