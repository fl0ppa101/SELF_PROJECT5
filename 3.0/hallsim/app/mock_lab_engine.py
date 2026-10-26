"""Canned laboratory data for UI development; not a physical model."""

import numpy as np
from hallsim.core.contracts import (
    FieldPoint,
    HallReading,
    AngularScanResult,
    SensorStudyCurve,
    PathProfile,
    ExperimentComparison,
)
from hallsim.core.enums import FieldStatus, SensorStudyAxis


class MockLabEngine:
    is_mock = True

    def compute_field_at(self, magnets, x_mm, y_mm):
        return FieldPoint(2.0, 1.0, 2.236, 26.565, FieldStatus.OK)

    def compute_hall_from_field(self, field, sensor_angle_deg, params):
        angles = np.linspace(0, 360, 361)
        fixture = 0.05 * np.cos(np.deg2rad(angles))
        value = float(np.interp(sensor_angle_deg % 360, angles, fixture))
        return HallReading(field, sensor_angle_deg, 1.0, value)

    def reconstruct_modB_from_hall_voltage(self, voltage, params):
        return float(voltage) * 40

    def compute_angular_scan_at(self, magnets, *, x_mm, y_mm, params, angular_step_deg):
        angles = np.arange(0, 360, angular_step_deg)
        fixture = 0.05 * np.cos(np.deg2rad(angles))
        return AngularScanResult(
            x_mm,
            y_mm,
            angles,
            fixture,
            0.05,
            2.0,
            self.compute_field_at(magnets, x_mm, y_mm),
        )

    def compute_sensor_study_curve(
        self, field, params, sensor_angle_deg, axis, x_values
    ):
        x = np.array(x_values, copy=True)
        if axis is SensorStudyAxis.ANGLE:
            values = 0.05 * np.cos(np.deg2rad(x))
            unit = "°"
        elif axis is SensorStudyAxis.CURRENT:
            values = np.linspace(0, 0.1, len(x))
            unit = "мА"
        else:
            values = np.linspace(0.1, 0.01, len(x))
            unit = "мм"
        return SensorStudyCurve(axis, x, values, unit)

    def compare_experiment(self, magnets, path, points, *, scene_revision=0):
        distances = np.array([p.s_mm for p in points])
        measured = np.array([p.measured_modB_mT for p in points])
        theory = np.full(len(points), 2.2)
        errors = abs(theory - measured)
        length = np.hypot(path.bx_mm - path.ax_mm, path.by_mm - path.ay_mm)
        profile = PathProfile(
            np.linspace(0, length, 500),
            np.full(500, 2.2),
            np.ones(500, dtype=bool),
            scene_revision,
        )
        return ExperimentComparison(
            distances,
            measured,
            theory,
            errors,
            float(errors.mean()) if len(points) else float("nan"),
            profile,
        )
