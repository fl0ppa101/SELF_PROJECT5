"""One running and one latest pending experiment; cancellation between points."""

from copy import deepcopy
from threading import Event
import numpy as np
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from hallsim.core.contracts import ExperimentPointResult
from hallsim.core.enums import MeasurementSource


class _Signals(QObject):
    point = pyqtSignal(object, int)
    progress = pyqtSignal(int, int, int)
    done = pyqtSignal(int, str, bool)


class _ExperimentJob(QRunnable):
    def __init__(self, engine, scene, params, count, step, run_id):
        super().__init__()
        self.engine = engine
        self.scene = deepcopy(scene)
        self.params = params
        self.count, self.step, self.run_id = count, step, run_id
        self.cancelled = Event()
        self.signals = _Signals()

    def run(self):
        error = ""
        try:
            p = self.scene.path
            length = float(np.hypot(p.bx_mm - p.ax_mm, p.by_mm - p.ay_mm))
            for index, t in enumerate(np.linspace(0, 1, self.count)):
                if self.cancelled.is_set():
                    break
                x, y = p.ax_mm + t * (p.bx_mm - p.ax_mm), p.ay_mm + t * (
                    p.by_mm - p.ay_mm
                )
                scan = self.engine.compute_angular_scan_at(
                    self.scene.magnets,
                    x_mm=float(x),
                    y_mm=float(y),
                    params=self.params,
                    angular_step_deg=self.step,
                )
                result = ExperimentPointResult(
                    float(t * length),
                    float(x),
                    float(y),
                    MeasurementSource.AUTOMATIC,
                    len(scan.angles_deg),
                    scan.max_abs_hall_voltage_mV,
                    scan.measured_modB_mT,
                )
                if self.cancelled.is_set():
                    break
                self.signals.point.emit(result, self.run_id)
                self.signals.progress.emit(index + 1, self.count, self.run_id)
        except Exception as exc:
            error = str(exc)
        self.signals.done.emit(self.run_id, error, self.cancelled.is_set())


class ExperimentService(QObject):
    pointReady = pyqtSignal(object, int)
    progressChanged = pyqtSignal(int, int, int)
    finished = pyqtSignal(int)
    failed = pyqtSignal(str, int)
    cancelled = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.running = None
        self.pending = None
        self.closed = False

    def start(self, engine, scene, params, count, step, run_id):
        self.cancel()
        self.pending = _ExperimentJob(engine, scene, params, count, step, run_id)
        if self.running is None:
            self._start_pending()

    def _start_pending(self):
        if self.closed or self.pending is None:
            return
        self.running, self.pending = self.pending, None
        signals = self.running.signals
        signals.point.connect(self.pointReady)
        signals.progress.connect(self.progressChanged)
        signals.done.connect(self._done)
        self.pool.start(self.running)

    def _done(self, run_id, error, cancelled):
        self.running = None
        if not self.closed:
            if cancelled:
                self.cancelled.emit(run_id)
            elif error:
                self.failed.emit(error, run_id)
            else:
                self.finished.emit(run_id)
            self._start_pending()

    def cancel(self):
        self.pending = None
        if self.running is not None:
            self.running.cancelled.set()

    def shutdown(self):
        self.closed = True
        self.cancel()
        self.pool.waitForDone()
