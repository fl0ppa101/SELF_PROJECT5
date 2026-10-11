"""Synthetic display provider, independent from hallsim.physics."""

from copy import deepcopy
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from hallsim.visualization.mock_data import mock_grid, mock_profile, mock_reading


class MockCalculationService(QObject):
    fieldGridReady = pyqtSignal(object)
    sensorReadingReady = pyqtSignal(object)
    pathProfileReady = pyqtSignal(object)
    calculationFailed = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.latest = None
        self.grid = None
        self.closed = False

    def update_scene(self, scene):
        self.latest = deepcopy(scene)

    def _emit(self, signal, result, revision):
        QTimer.singleShot(
            0,
            lambda: (
                signal.emit(result)
                if not self.closed
                and self.latest is not None
                and revision == self.latest.revision
                else None
            ),
        )

    def request_field_grid(self, scene, quality):
        self.update_scene(scene)
        self.grid = mock_grid(scene, quality)
        self._emit(self.fieldGridReady, self.grid, scene.revision)

    def request_sensor_reading(self, scene):
        self.update_scene(scene)
        grid = self.grid if self.grid is not None else mock_grid(scene, "drag")
        self._emit(
            self.sensorReadingReady, mock_reading(grid, scene.sensor), scene.revision
        )

    def request_path_profile(self, scene):
        self.update_scene(scene)
        grid = self.grid if self.grid is not None else mock_grid(scene, "drag")
        self._emit(
            self.pathProfileReady,
            mock_profile(grid, scene.path, scene.revision),
            scene.revision,
        )

    def shutdown(self):
        self.closed = True
