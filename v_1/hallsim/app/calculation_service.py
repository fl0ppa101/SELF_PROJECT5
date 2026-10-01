"""Bounded asynchronous Physics API adapter. Qt stays outside the physics module."""
from copy import deepcopy
from dataclasses import replace
import time

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal

from hallsim.app.config import DRAG_GRID_SIZE, FULL_GRID_SIZE, X_MIN_MM, X_MAX_MM, Y_MIN_MM, Y_MAX_MM
from hallsim.core.magnet_catalog import MAGNET_CATALOG
from hallsim.physics.engine import PhysicsEngine


def magnet_key(scene):
    return tuple((m.id, m.enabled, m.x_mm, m.y_mm, m.angle_deg, m.definition_id) for m in scene.magnets)


def dependency_key(kind, scene):
    magnets = magnet_key(scene)
    if kind == "field":
        return magnets
    if kind == "sensor":
        s = scene.sensor
        return magnets, s.x_mm, s.y_mm, s.angle_deg, s.orientation_mode
    p = scene.path
    return magnets, p.enabled, p.ax_mm, p.ay_mm, p.bx_mm, p.by_mm, p.samples


class _Signals(QObject):
    done = pyqtSignal(int, object, str)


class _Job(QRunnable):
    def __init__(self, engine, kind, scene, quality, token):
        super().__init__()
        self.engine, self.kind, self.scene = engine, kind, scene
        self.quality, self.token = quality, token
        self.signals = _Signals()

    def run(self):
        try:
            scene = self.scene
            if self.kind == "field":
                nx, ny = DRAG_GRID_SIZE if self.quality == "drag" else FULL_GRID_SIZE
                result = self.engine.compute_field_grid(
                    scene.magnets, xmin_mm=X_MIN_MM, xmax_mm=X_MAX_MM,
                    ymin_mm=Y_MIN_MM, ymax_mm=Y_MAX_MM, nx=nx, ny=ny,
                    scene_revision=scene.revision,
                )
                for values in (result.x_mm, result.y_mm, result.bx_mT, result.by_mT,
                               result.modB_mT, result.valid_mask):
                    values.flags.writeable = False
            elif self.kind == "sensor":
                result = self.engine.compute_sensor_reading(scene.magnets, scene.sensor)
            elif scene.path.enabled:
                result = self.engine.compute_path_profile(scene.magnets, scene.path, scene_revision=scene.revision)
            else:
                result = None
            self.signals.done.emit(self.token, result, "")
        except Exception as exc:
            self.signals.done.emit(self.token, None, str(exc))


class _Queue(QObject):
    """At most one running and one latest pending task for each result kind."""
    def __init__(self, service, kind):
        super().__init__(service)
        self.service, self.kind = service, kind
        self.token = 0
        self.running = None
        self.pending = None
        self.last_started = 0.
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._start)

    def submit(self, scene, quality):
        self.token += 1
        self.pending = (deepcopy(scene), quality, self.token, self.service.catalog_revision)
        if self.running is None:
            self._schedule()

    def _schedule(self):
        if self.pending is None or self.service.closed:
            return
        quality = self.pending[1]
        wait = max(0., 1/30-(time.monotonic()-self.last_started)) if quality == "drag" else 0.
        self.timer.start(int(wait*1000))

    def _start(self):
        if self.running is not None or self.pending is None or self.service.closed:
            return
        scene, quality, token, catalog_revision = self.pending
        self.pending = None
        job = _Job(self.service.engine, self.kind, scene, quality, token)
        self.running = (job, catalog_revision)
        job.signals.done.connect(self._finished)
        self.last_started = time.monotonic()
        self.service.pool.start(job)

    def _finished(self, token, result, error):
        job, catalog_revision = self.running
        self.running = None
        current = self.service.latest_scene
        if (not self.service.closed and token == self.token and current is not None
                and catalog_revision == self.service.catalog_revision
                and dependency_key(self.kind, job.scene) == dependency_key(self.kind, current)):
            if error:
                self.service.calculationFailed.emit(error, current.revision)
            elif self.kind == "sensor":
                self.service.sensorReadingReady.emit(result)
            elif self.kind == "field":
                # Sensor/path edits do not change a field grid. Publish the same
                # immutable arrays for the current scene only after verifying inputs.
                self.service.fieldGridReady.emit(replace(result, scene_revision=current.revision))
            else:
                self.service.pathProfileReady.emit(None if result is None else replace(result, scene_revision=current.revision))
        if self.pending is not None:
            self._schedule()


class CalculationService(QObject):
    fieldGridReady = pyqtSignal(object)
    sensorReadingReady = pyqtSignal(object)
    pathProfileReady = pyqtSignal(object)
    calculationFailed = pyqtSignal(str, int)

    def __init__(self, magnet_catalog=None, parent=None):
        super().__init__(parent)
        self.engine = PhysicsEngine(MAGNET_CATALOG if magnet_catalog is None else magnet_catalog)
        self.catalog_revision = 0
        self.latest_scene = None
        self.closed = False
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(3)
        self.queues = {kind: _Queue(self, kind) for kind in ("field", "sensor", "path")}

    def update_scene(self, scene):
        self.latest_scene = deepcopy(scene)

    def update_catalog(self, catalog):
        self.engine = PhysicsEngine(catalog)
        self.catalog_revision += 1

    def optimal_sensor_angle(self, scene):
        return self.engine.compute_optimal_sensor_angle(scene.magnets, scene.sensor.x_mm, scene.sensor.y_mm)

    def field_at(self, scene, x_mm, y_mm):
        return self.engine.compute_field_at(scene.magnets, x_mm, y_mm)

    def request_field_grid(self, scene, quality):
        if quality not in {"drag", "full"}:
            raise ValueError("quality must be drag or full")
        self.update_scene(scene)
        self.queues["field"].submit(scene, quality)

    def request_sensor_reading(self, scene):
        self.update_scene(scene)
        self.queues["sensor"].submit(scene, "full")

    def request_path_profile(self, scene):
        self.update_scene(scene)
        self.queues["path"].submit(scene, "full")

    def shutdown(self):
        self.closed = True
        for queue in self.queues.values():
            queue.timer.stop()
            queue.pending = None
        self.pool.waitForDone()
