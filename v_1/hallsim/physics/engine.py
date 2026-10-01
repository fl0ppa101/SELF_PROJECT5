"""Публичный API: хранение настроек и вызовы расчётных функций."""

from hallsim.core.contracts import (
    FieldGrid,
    FieldPoint,
    MagnetDefinition,
    MagnetState,
    PathProfile,
    PathState,
    SensorReading,
    SensorState,
)

from . import field
from . import path as path_calculations
from . import sensor as sensor_calculations
from .validation import copy_catalog, positive_real


class PhysicsEngine:
    """Координаты в мм, углы в градусах, поле в мТл."""

    def __init__(
        self,
        magnet_catalog: dict[str, MagnetDefinition],
        *,
        singularity_radius_mm: float = 0.5,
        zero_field_epsilon_mT: float = 1e-6,
    ) -> None:
        self._magnet_catalog = copy_catalog(magnet_catalog)
        self._singularity_radius_mm = positive_real(
            singularity_radius_mm, "singularity_radius_mm",
        )
        self._zero_field_epsilon_mT = positive_real(
            zero_field_epsilon_mT, "zero_field_epsilon_mT",
        )

    def compute_field_at(
        self,
        magnets: list[MagnetState],
        x_mm: float,
        y_mm: float,
    ) -> FieldPoint:
        return field.compute_field_at(
            magnets, self._magnet_catalog, x_mm, y_mm,
            singularity_radius_mm=self._singularity_radius_mm,
            zero_field_epsilon_mT=self._zero_field_epsilon_mT,
        )

    def compute_field_grid(
        self,
        magnets: list[MagnetState],
        *,
        xmin_mm: float,
        xmax_mm: float,
        ymin_mm: float,
        ymax_mm: float,
        nx: int,
        ny: int,
        scene_revision: int,
    ) -> FieldGrid:
        return field.compute_field_grid(
            magnets, self._magnet_catalog,
            xmin_mm=xmin_mm, xmax_mm=xmax_mm,
            ymin_mm=ymin_mm, ymax_mm=ymax_mm, nx=nx, ny=ny,
            scene_revision=scene_revision,
            singularity_radius_mm=self._singularity_radius_mm,
        )

    def compute_sensor_reading(
        self,
        magnets: list[MagnetState],
        sensor: SensorState,
    ) -> SensorReading:
        return sensor_calculations.compute_sensor_reading(
            magnets, self._magnet_catalog, sensor,
            singularity_radius_mm=self._singularity_radius_mm,
            zero_field_epsilon_mT=self._zero_field_epsilon_mT,
        )

    def compute_optimal_sensor_angle(
        self,
        magnets: list[MagnetState],
        x_mm: float,
        y_mm: float,
    ) -> float | None:
        return sensor_calculations.compute_optimal_sensor_angle(
            magnets, self._magnet_catalog, x_mm, y_mm,
            singularity_radius_mm=self._singularity_radius_mm,
            zero_field_epsilon_mT=self._zero_field_epsilon_mT,
        )

    def compute_path_profile(
        self,
        magnets: list[MagnetState],
        path: PathState,
        *,
        scene_revision: int,
    ) -> PathProfile:
        return path_calculations.compute_path_profile(
            magnets, self._magnet_catalog, path,
            scene_revision=scene_revision,
            singularity_radius_mm=self._singularity_radius_mm,
        )
