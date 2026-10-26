"""Independent laboratory states, immutable setup snapshot and cached readings."""

from copy import deepcopy
from dataclasses import replace
import math
import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from hallsim.core.contracts import (
    ExperimentConfig,
    ExperimentPathState,
    ExperimentState,
    ExperimentPointResult,
    SensorStudyState,
)
from hallsim.core.enums import (
    MeasurementSource,
    SensorOrientationMode,
    SensorStudyAxis,
    FieldStatus,
)
from hallsim.core.sensor_catalog import EDUCATIONAL_SENSOR, POINT_MERGE_EPSILON_MM
from .controller import AppController
from .experiment_service import ExperimentService
from .presets import single_magnet
from ..visualization.experiment_layer import project_to_segment


def magnet_key(scene):
    return tuple(
        (m.id, m.enabled, m.x_mm, m.y_mm, m.angle_deg, m.definition_id)
        for m in scene.magnets
    )


class ExperimentController(QObject):
    changed = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, engine, catalog_service, parent=None):
        super().__init__(parent)
        scene = single_magnet()
        scene.sensor.orientation_mode = SensorOrientationMode.MANUAL
        scene.view.show_heatmap = scene.view.show_field_lines = False
        self.scene_controller = AppController(
            scene=scene, catalog_service=catalog_service, parent=self
        )
        self.scene_controller.sceneChanged.connect(self._scene_changed)
        p = scene.path
        self.state = ExperimentState(
            ExperimentPathState(p.enabled, p.ax_mm, p.ay_mm, p.bx_mm, p.by_mm),
            ExperimentConfig(),
            EDUCATIONAL_SENSOR,
        )
        self.engine = engine
        self.snapshot = None
        self.snapshot_engine = None
        self.active = None
        self.active_field = None
        self.reading = None
        self.captures = []
        self.comparison = None
        self.pending = []
        self.run_id = 0
        self.running = False
        self.progress = (0, 0)
        self.service = ExperimentService(self)
        self.service.pointReady.connect(self._point_ready)
        self.service.progressChanged.connect(self._progress)
        self.service.finished.connect(self._finished)
        self.service.failed.connect(self._failed)

    def scene(self):
        return self.scene_controller.scene()

    def _scene_changed(self, scene):
        p = scene.path
        self.state.path = ExperimentPathState(
            p.enabled, p.ax_mm, p.ay_mm, p.bx_mm, p.by_mm
        )
        scene.sensor.orientation_mode = SensorOrientationMode.MANUAL
        self.changed.emit()

    def blocked(self):
        self.message.emit(
            "Эксперимент уже начат. Чтобы изменить установку, начните эксперимент заново."
        )

    def edit_scene(self, method, *args, **kwargs):
        if self.state.locked:
            self.blocked()
            return
        getattr(self.scene_controller, method)(*args, **kwargs)
        self.scene_controller._scene.sensor.orientation_mode = (
            SensorOrientationMode.MANUAL
        )
        self.scene_controller._scene.view.show_heatmap = False
        self.scene_controller._scene.view.show_field_lines = False
        self.changed.emit()

    def set_config(self, count, step):
        if self.running:
            raise ValueError("Дождитесь окончания автоматического измерения")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or not 2 <= count <= 200
        ):
            raise ValueError("Количество точек: от 2 до 200")
        if not math.isfinite(step) or not 0 < step < 360:
            raise ValueError("Шаг поворота должен быть больше 0 и меньше 360°")
        self.state.config = ExperimentConfig(count, float(step))

    def _validate_path(self):
        p = self.state.path
        if not p.enabled or math.hypot(p.bx_mm - p.ax_mm, p.by_mm - p.ay_mm) < 1e-6:
            raise ValueError("Задайте две разные точки A и B")

    def _lock(self):
        if not self.state.locked:
            self._validate_path()
            self.snapshot = self.scene()
            self.snapshot_engine = self.engine
            self.state.locked = True

    def activate_manual_point(self, s_mm, x_mm, y_mm):
        if self.running:
            raise ValueError("Дождитесь окончания автоматического измерения")
        if self.active is not None and self.captures:
            raise ValueError("Сначала завершите или отмените текущую точку")
        self._validate_path()
        if not np.isfinite([s_mm, x_mm, y_mm]).all():
            raise ValueError("Некорректные координаты точки")
        projected = project_to_segment(self.state.path, x_mm, y_mm)
        if (
            projected is None
            or math.hypot(projected[1] - x_mm, projected[2] - y_mm) > 1e-6
            or abs(projected[0] - s_mm) > 1e-6
        ):
            raise ValueError("Ручная точка должна лежать на отрезке A–B")
        source = self.snapshot if self.state.locked else self.scene()
        engine = self.snapshot_engine if self.state.locked else self.engine
        field = engine.compute_field_at(source.magnets, x_mm, y_mm)
        if field.status in (FieldStatus.INSIDE_SINGULARITY, FieldStatus.INVALID_INPUT):
            raise ValueError("Недопустимая точка: слишком близко к центру магнита")
        self._lock()
        self.active = projected
        self.active_field = field
        self.captures = []
        sensor = self.scene_controller._scene.sensor
        sensor.x_mm, sensor.y_mm = x_mm, y_mm
        self.rotate_sensor(sensor.angle_deg)

    def select_point(self, s_mm):
        point = next(
            (
                p
                for p in self.state.points
                if abs(p.s_mm - s_mm) < POINT_MERGE_EPSILON_MM
            ),
            None,
        )
        if point is not None:
            self.activate_manual_point(point.s_mm, point.x_mm, point.y_mm)

    def rotate_sensor(self, angle):
        if self.active is None or self.running:
            return
        angle = AppController._angle(angle)
        self.scene_controller._scene.sensor.angle_deg = angle
        self.reading = self.snapshot_engine.compute_hall_from_field(
            self.active_field, angle, self.state.sensor_params
        )
        self.changed.emit()

    def capture(self):
        if (
            self.reading is None
            or self.active is None
            or not math.isfinite(self.reading.hall_voltage_mV)
        ):
            raise ValueError("Выберите допустимую ручную точку")
        self.captures.append(self.reading.hall_voltage_mV)
        self.changed.emit()

    def finish_manual_point(self):
        if self.active is None or not self.captures:
            raise ValueError("Снимите хотя бы одно измерение")
        s, x, y = self.active
        maximum = max(abs(value) for value in self.captures)
        value = self.snapshot_engine.reconstruct_modB_from_hall_voltage(
            maximum, self.state.sensor_params
        )
        self._merge(
            ExperimentPointResult(
                s, x, y, MeasurementSource.MANUAL, len(self.captures), maximum, value
            )
        )
        self.cancel_manual_point()

    def cancel_manual_point(self):
        self.active = None
        self.active_field = None
        self.captures = []
        self.reading = None
        self.changed.emit()

    def _merge(self, point):
        self.state.points = [
            p
            for p in self.state.points
            if abs(p.s_mm - point.s_mm) >= POINT_MERGE_EPSILON_MM
        ]
        self.state.points.append(point)
        self.state.points.sort(key=lambda p: p.s_mm)
        self.comparison = None

    def start_automatic(self):
        if self.running:
            return
        if self.active is not None:
            raise ValueError("Завершите или отмените текущую ручную точку")
        self._lock()
        self.run_id += 1
        self.running = True
        self.comparison = None
        count = self.state.config.automatic_point_count
        p = self.state.path
        length = math.hypot(p.bx_mm - p.ax_mm, p.by_mm - p.ay_mm)
        self.pending = [
            (
                float(t * length),
                float(p.ax_mm + t * (p.bx_mm - p.ax_mm)),
                float(p.ay_mm + t * (p.by_mm - p.ay_mm)),
            )
            for t in np.linspace(0, 1, count)
        ]
        self.progress = (0, count)
        self.service.start(
            self.snapshot_engine,
            self.snapshot,
            self.state.sensor_params,
            count,
            self.state.config.angular_step_deg,
            self.run_id,
        )
        self.changed.emit()

    def _point_ready(self, point, run_id):
        if run_id != self.run_id or not self.running:
            return
        self._merge(point)
        self.pending = [
            p for p in self.pending if abs(p[0] - point.s_mm) >= POINT_MERGE_EPSILON_MM
        ]
        self.scene_controller._scene.sensor.x_mm = point.x_mm
        self.scene_controller._scene.sensor.y_mm = point.y_mm
        self.changed.emit()

    def _progress(self, completed, total, run_id):
        if run_id == self.run_id and self.running:
            self.progress = (completed, total)
            self.changed.emit()

    def _finished(self, run_id):
        if run_id == self.run_id:
            self.running = False
            self.pending = []
            self.changed.emit()

    def _failed(self, error, run_id):
        if run_id == self.run_id:
            self._finished(run_id)
            self.message.emit(error)

    def compare(self):
        if self.running or not self.state.points:
            raise ValueError("Сначала завершите измерения")
        self.comparison = self.snapshot_engine.compare_experiment(
            self.snapshot.magnets,
            self.snapshot.path,
            self.state.points,
            scene_revision=self.snapshot.revision,
        )
        self.changed.emit()

    def reset(self):
        self.run_id += 1
        self.service.cancel()
        self.running = False
        self.state.points = []
        self.state.locked = False
        self.snapshot = self.snapshot_engine = None
        self.comparison = None
        self.pending = []
        self.progress = (0, 0)
        self.cancel_manual_point()

    def shutdown(self):
        self.service.shutdown()


class SensorStudyController(QObject):
    changed = pyqtSignal()
    curveChanged = pyqtSignal(object)

    def __init__(self, engine, catalog_service, parent=None):
        super().__init__(parent)
        scene = single_magnet()
        scene.sensor.orientation_mode = SensorOrientationMode.MANUAL
        scene.view.show_heatmap = scene.view.show_field_lines = False
        self.scene_controller = AppController(
            scene=scene, catalog_service=catalog_service, parent=self
        )
        self.engine = engine
        self.state = SensorStudyState(replace(EDUCATIONAL_SENSOR))
        self.field = None
        self.reading = None
        self.curve = None
        self.field_key = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(60)
        self.timer.timeout.connect(self._compute_curve)
        self.scene_controller.sceneChanged.connect(lambda scene: self.refresh())
        self.refresh()

    def scene(self):
        return self.scene_controller.scene()

    def edit_scene(self, method, *args, **kwargs):
        getattr(self.scene_controller, method)(*args, **kwargs)

    def refresh(self):
        scene = self.scene()
        key = (id(self.engine), magnet_key(scene), scene.sensor.x_mm, scene.sensor.y_mm)
        if key != self.field_key:
            self.field = self.engine.compute_field_at(
                scene.magnets, scene.sensor.x_mm, scene.sensor.y_mm
            )
            self.field_key = key
        self.reading = self.engine.compute_hall_from_field(
            self.field, scene.sensor.angle_deg, self.state.sensor_params
        )
        self.changed.emit()
        self.timer.start()

    def set_parameters(self, current, thickness, coefficient):
        if not np.isfinite([current, thickness, coefficient]).all() or thickness <= 0:
            raise ValueError("Требуются конечные параметры и положительная толщина")
        self.state.sensor_params = replace(
            self.state.sensor_params,
            current_mA=float(current),
            thickness_mm=float(thickness),
            hall_coefficient_m3_C=float(coefficient),
        )
        self.refresh()

    def set_axis(self, axis):
        if not isinstance(axis, SensorStudyAxis):
            raise ValueError("Неизвестный график")
        self.state.selected_axis = axis
        self.changed.emit()
        self.timer.start()

    def _compute_curve(self):
        p = self.state.sensor_params
        axis = self.state.selected_axis
        if axis is SensorStudyAxis.CURRENT:
            x = np.linspace(0, max(20.0, 2 * abs(p.current_mA)), 300)
        elif axis is SensorStudyAxis.THICKNESS:
            x = np.linspace(
                max(0.0001, 0.25 * p.thickness_mm), min(10.0, 2 * p.thickness_mm), 300
            )
        else:
            x = np.linspace(0, 360, 361)
        self.curve = self.engine.compute_sensor_study_curve(
            self.field, p, self.scene().sensor.angle_deg, axis, x
        )
        self.curveChanged.emit(self.curve)
