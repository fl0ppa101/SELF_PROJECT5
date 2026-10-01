from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from hallsim.app.config import (
    DRAG_GRID_SIZE,
    FULL_GRID_SIZE,
    X_MAX_MM,
    X_MIN_MM,
    Y_MAX_MM,
    Y_MIN_MM,
)
from hallsim.core.contracts import FieldGrid, FieldPoint, PathProfile, SensorReading
from hallsim.core.enums import FieldStatus


class MockCalculationService(QObject):
    """Deterministic non-physical provider used until Physics is connected."""

    fieldGridReady = pyqtSignal(object)
    sensorReadingReady = pyqtSignal(object)
    pathProfileReady = pyqtSignal(object)
    calculationFailed = pyqtSignal(str, int)

    def request_field_grid(self, scene, quality: str) -> None:
        nx, ny = DRAG_GRID_SIZE if quality == "drag" else FULL_GRID_SIZE
        x_mm = np.linspace(X_MIN_MM, X_MAX_MM, nx, dtype=np.float64)
        y_mm = np.linspace(Y_MIN_MM, Y_MAX_MM, ny, dtype=np.float64)
        shape = (ny, nx)
        zeros = np.zeros(shape, dtype=np.float64)
        grid = FieldGrid(
            x_mm=x_mm,
            y_mm=y_mm,
            bx_mT=zeros.copy(),
            by_mT=zeros.copy(),
            modB_mT=zeros.copy(),
            valid_mask=np.ones(shape, dtype=np.bool_),
            scene_revision=scene.revision,
        )
        QTimer.singleShot(0, lambda: self.fieldGridReady.emit(grid))

    def request_sensor_reading(self, scene) -> None:
        point = FieldPoint(0.0, 0.0, 0.0, None, FieldStatus.ZERO_FIELD)
        reading = SensorReading(value_mT=0.0, field=point)
        QTimer.singleShot(0, lambda: self.sensorReadingReady.emit(reading))

    def request_path_profile(self, scene) -> None:
        samples = scene.path.samples
        dx = scene.path.bx_mm - scene.path.ax_mm
        dy = scene.path.by_mm - scene.path.ay_mm
        length = float(np.hypot(dx, dy))
        distance = np.linspace(0.0, length, samples, dtype=np.float64)
        profile = PathProfile(
            distance_mm=distance,
            modB_mT=np.zeros(samples, dtype=np.float64),
            valid_mask=np.ones(samples, dtype=np.bool_),
            scene_revision=scene.revision,
        )
        QTimer.singleShot(0, lambda: self.pathProfileReady.emit(profile))

