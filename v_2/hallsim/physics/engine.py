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
from . import hall
from hallsim.core.enums import SensorStudyAxis


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
            singularity_radius_mm,
            "singularity_radius_mm",
        )
        self._zero_field_epsilon_mT = positive_real(
            zero_field_epsilon_mT,
            "zero_field_epsilon_mT",
        )

    def compute_field_at(
        self,
        magnets: list[MagnetState],
        x_mm: float,
        y_mm: float,
    ) -> FieldPoint:
        return field.compute_field_at(
            magnets,
            self._magnet_catalog,
            x_mm,
            y_mm,
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
            magnets,
            self._magnet_catalog,
            xmin_mm=xmin_mm,
            xmax_mm=xmax_mm,
            ymin_mm=ymin_mm,
            ymax_mm=ymax_mm,
            nx=nx,
            ny=ny,
            scene_revision=scene_revision,
            singularity_radius_mm=self._singularity_radius_mm,
        )

    def compute_sensor_reading(
        self,
        magnets: list[MagnetState],
        sensor: SensorState,
    ) -> SensorReading:
        return sensor_calculations.compute_sensor_reading(
            magnets,
            self._magnet_catalog,
            sensor,
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
            magnets,
            self._magnet_catalog,
            x_mm,
            y_mm,
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
            magnets,
            self._magnet_catalog,
            path,
            scene_revision=scene_revision,
            singularity_radius_mm=self._singularity_radius_mm,
        )

    def compute_hall_from_field(self, field, sensor_angle_deg, params):
        return hall.compute_hall_from_field(field, sensor_angle_deg, params)

    def compute_hall_reading(self, magnets, sensor, params):
        point = self.compute_field_at(magnets, sensor.x_mm, sensor.y_mm)
        return self.compute_hall_from_field(point, sensor.angle_deg, params)

    def reconstruct_modB_from_hall_voltage(self, max_abs_hall_voltage_mV, params):
        return hall.reconstruct_modB_from_hall_voltage(max_abs_hall_voltage_mV, params)

    def compute_angular_scan_at(self, magnets, *, x_mm, y_mm, params, angular_step_deg):
        import numpy as np
        from hallsim.core.contracts import AngularScanResult

        step = positive_real(angular_step_deg, "angular_step_deg")
        if step >= 360:
            raise ValueError("Шаг угла должен быть меньше 360°")
        hall.validate_parameters(params, reconstruction=True)
        angles = np.arange(0.0, 360.0, step)
        angles = angles[angles < 360]
        point = self.compute_field_at(magnets, x_mm, y_mm)
        curve = hall.compute_sensor_study_curve(
            point, params, 0.0, SensorStudyAxis.ANGLE, angles
        )
        maximum = float(np.max(np.abs(curve.hall_voltage_mV)))
        measured = (
            self.reconstruct_modB_from_hall_voltage(maximum, params)
            if np.isfinite(maximum)
            else float("nan")
        )
        return AngularScanResult(
            float(x_mm),
            float(y_mm),
            angles,
            curve.hall_voltage_mV,
            maximum,
            measured,
            point,
        )

    def compute_sensor_study_curve(
        self, field, params, sensor_angle_deg, axis, x_values
    ):
        return hall.compute_sensor_study_curve(
            field, params, sensor_angle_deg, axis, x_values
        )

    def compute_theoretical_modB_at_distances(self, magnets, path, distance_mm):
        import numpy as np
        from .validation import finite_real

        coordinates = [
            finite_real(getattr(path, name), name)
            for name in ("ax_mm", "ay_mm", "bx_mm", "by_mm")
        ]
        ax, ay, bx, by = coordinates
        length = np.hypot(bx - ax, by - ay)
        if length <= 0:
            raise ValueError("Точки A и B должны различаться")
        distances = np.asarray(distance_mm, dtype=float)
        if (
            distances.ndim != 1
            or not np.isfinite(distances).all()
            or np.any(distances < 0)
            or np.any(distances > length + 1e-8)
        ):
            raise ValueError("Расстояния должны лежать на отрезке A–B")
        t = np.clip(distances / length, 0, 1)
        bx_values, by_values, valid = field.field_components_at_points(
            magnets,
            self._magnet_catalog,
            ax + t * (bx - ax),
            ay + t * (by - ay),
            singularity_radius_mm=self._singularity_radius_mm,
        )
        return np.hypot(bx_values, by_values)

    def compare_experiment(self, magnets, path, points, *, scene_revision=0):
        import numpy as np
        from hallsim.core.contracts import ExperimentComparison, PathState

        ordered = sorted(points, key=lambda point: point.s_mm)
        distances = np.array([p.s_mm for p in ordered])
        measured = np.array([p.measured_modB_mT for p in ordered])
        theory = self.compute_theoretical_modB_at_distances(magnets, path, distances)
        errors = np.abs(measured - theory)
        finite = np.isfinite(errors)
        mean = float(errors[finite].mean()) if finite.any() else float("nan")
        dense_path = PathState(
            True, path.ax_mm, path.ay_mm, path.bx_mm, path.by_mm, 500
        )
        profile = self.compute_path_profile(
            magnets, dense_path, scene_revision=scene_revision
        )
        return ExperimentComparison(distances, measured, theory, errors, mean, profile)
