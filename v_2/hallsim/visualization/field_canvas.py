"""Field view and interactions. All public positions and signals use millimeters."""

from copy import deepcopy
import math
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QEvent, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import QHBoxLayout, QWidget
from hallsim.core.contracts import FieldGrid, SceneState, SensorReading, ViewSettings
from .heatmap_layer import ColorBar, HeatmapLayer
from .object_layer import ObjectLayer
from .path_layer import PathLayer
from .streamline_layer import StreamlineLayer
from .theme import get_theme
from hallsim.core.enums import AppSection
from .experiment_layer import ExperimentLayer, project_to_segment
from .axes import fixed_units_axis


class FieldCanvas(QWidget):
    experimentPointRequested = pyqtSignal(float, float, float)
    experimentPointSelected = pyqtSignal(float)
    interactionBlocked = pyqtSignal()
    actionCancelled = pyqtSignal()
    magnetDragStarted = pyqtSignal(int)
    magnetDragged = pyqtSignal(int, float, float)
    magnetDragFinished = pyqtSignal(int, float, float)
    magnetRotationStarted = pyqtSignal(int)
    magnetRotated = pyqtSignal(int, float)
    magnetRotationFinished = pyqtSignal(int, float)
    sensorDragStarted = pyqtSignal()
    sensorDragged = pyqtSignal(float, float)
    sensorDragFinished = pyqtSignal(float, float)
    sensorRotated = pyqtSignal(float)
    pathPointMoved = pyqtSignal(str, float, float)
    cursorWorldPositionChanged = pyqtSignal(float, float)
    objectSelected = pyqtSignal(str, int)
    viewTransformChanged = pyqtSignal(float)
    pathCreationFinished = pyqtSignal()
    visualizationError = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 280)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.graphics = pg.PlotWidget()
        self.graphics.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.plot = self.graphics.getPlotItem()
        self.plot.setMenuEnabled(False)
        self.plot.hideButtons()
        self.plot.setLabel("bottom", "X, мм")
        self.plot.setLabel("left", "Y, мм")
        for name in ("left", "bottom"):
            fixed_units_axis(self.plot.getAxis(name))
        self.view_box = self.plot.getViewBox()
        self.view_box.setAspectLocked(True, ratio=1)
        self.view_box.setDefaultPadding(0)
        self.view_box.disableAutoRange()
        self.colorbar = ColorBar()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(self.graphics, 1)
        layout.addWidget(self.colorbar)
        self.heatmap = HeatmapLayer(self.plot, self.colorbar)
        self.streamlines = StreamlineLayer(self.plot, self)
        self.streamlines.failed.connect(self.visualizationError)
        self.objects = ObjectLayer(self.plot)
        self.path = PathLayer(self.plot)
        self.experiment = ExperimentLayer(self.plot)
        self.mode = AppSection.VISUALIZATION
        self.locked = False
        self.sensor_translation_enabled = True
        self.sensor_rotation_enabled = True
        self._manual_tool = False
        self.scale_bar = pg.ScaleBar(size=20, suffix=" мм", offset=(-16, -16))
        self.scale_bar.setParentItem(self.view_box)
        self.scale_bar.anchor((1, 1), (1, 1), offset=(-16, -16))
        self.empty_label = pg.TextItem(anchor=(0.5, 0.5))
        self.empty_label.setZValue(50)
        self.plot.addItem(self.empty_label)
        self.empty_label.setText("Ожидание данных поля")
        self.scene = None
        self.grid = None
        self.reading = None
        self.theme_name = "light"
        self._active = None
        self._offset = (0.0, 0.0)
        self._pan = None
        self._last_position = None
        self._path_stage = None
        viewport = self.graphics.viewport()
        viewport.setMouseTracking(True)
        viewport.installEventFilter(self)
        self.view_box.sigRangeChanged.connect(self._view_changed)
        self._shortcuts = []
        for key, action in [
            ("R", self.reset_view),
            ("+", self.zoom_in),
            ("=", self.zoom_in),
            ("-", self.zoom_out),
            ("Escape", self.cancel_action),
        ]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(action)
            self._shortcuts.append(shortcut)
        self.set_theme("light")
        self.reset_view()

    def set_scene(self, scene: SceneState) -> None:
        previous_view = self.scene.view if self.scene is not None else None
        previous_magnets = self.scene.magnets if self.scene is not None else None
        self.scene = deepcopy(scene)
        if self.mode is not AppSection.VISUALIZATION:
            self.scene.view.show_heatmap = False
            self.scene.view.show_field_lines = False
        self.objects.set_scene(self.scene)
        self.path.set_path(self.scene.path)
        if previous_view != self.scene.view or previous_magnets != self.scene.magnets:
            density_changed = (
                previous_view is None
                or previous_view.line_density != self.scene.view.line_density
            )
            self.streamlines.density = self.scene.view.line_density
            self.heatmap.set_palette(self.scene.view.palette)
            self.heatmap.update(self.grid, self.scene.view, self.scene.magnets)
            self.plot.showGrid(
                x=self.scene.view.show_grid, y=self.scene.view.show_grid, alpha=0.12
            )
            self.streamlines.set_visible(self.scene.view.show_field_lines)
            if (
                self.scene.view.show_field_lines
                and (not self.streamlines.geometry or density_changed)
                and self.grid is not None
            ):
                self.streamlines.request(self.grid)

    def set_field_grid(self, grid: FieldGrid | None) -> None:
        if self.mode is not AppSection.VISUALIZATION:
            grid = None
        settings = self.scene.view if self.scene is not None else ViewSettings()
        self.heatmap.update(grid, settings, self.scene.magnets if self.scene else ())
        self.grid = grid
        self.empty_label.setVisible(
            grid is None and self.mode is AppSection.VISUALIZATION
        )
        self.streamlines.request(grid)

    def set_sensor_reading(self, reading: SensorReading | None) -> None:
        self.reading = reading

    def set_theme(self, theme: str) -> None:
        t = get_theme(theme)
        self.theme_name = theme
        self.graphics.setBackground(t.background)
        for name in ("left", "bottom"):
            axis = self.plot.getAxis(name)
            axis.setPen(pg.mkPen(t.border))
            axis.setTextPen(pg.mkPen(t.foreground))
            axis.setLabel("Y, мм" if name == "left" else "X, мм", color=t.foreground)
        self.colorbar.theme = t
        self.colorbar.update()
        self.objects.set_theme(theme)
        self.path.set_theme(theme)
        self.experiment.theme = theme
        self.experiment.refresh()
        self.streamlines.set_color(t.field_line)
        self.empty_label.setColor(t.muted)
        self.scale_bar.brush = pg.mkBrush(t.foreground)
        self.scale_bar.pen = pg.mkPen(t.foreground)
        self.scale_bar.bar.setBrush(self.scale_bar.brush)
        self.scale_bar.bar.setPen(self.scale_bar.pen)
        self.scale_bar.text.setColor(t.foreground)
        self.scale_bar.update()

    def set_interaction_quality(self, mode: str) -> None:
        if mode not in {"drag", "full"}:
            raise ValueError("interaction quality must be drag or full")
        old = self.streamlines.mode
        self.streamlines.mode = mode
        if mode == "full" and old == "drag" and self.grid is not None:
            self.streamlines.request(self.grid)

    def set_palette(self, name: str) -> None:
        self.heatmap.set_palette(name)

    def set_path_creation_enabled(self, enabled: bool) -> None:
        if enabled and self.locked:
            self.interactionBlocked.emit()
            return
        self._path_stage = "A" if enabled else None
        self.graphics.viewport().setCursor(
            Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor
        )

    def set_mode(self, mode):
        self.mode = mode
        self.colorbar.setVisible(mode is AppSection.VISUALIZATION)
        self.experiment.markers.setVisible(mode is AppSection.EXPERIMENT)
        self.empty_label.setVisible(
            mode is AppSection.VISUALIZATION and self.grid is None
        )
        if self.scene is not None:
            self.set_scene(self.scene)
        if mode is not AppSection.VISUALIZATION:
            self.set_field_grid(None)

    def set_hall_reading(self, reading):
        self.reading = reading

    def set_path(self, path):
        if self.scene is not None:
            self.scene.path = deepcopy(path)
        self.path.set_path(path)

    def set_experiment_points(self, points):
        self.experiment.points = list(points)
        self.experiment.refresh()

    def set_experiment_pending_points(self, points):
        self.experiment.pending = list(points)
        self.experiment.refresh()

    def set_active_experiment_point(self, point):
        self.experiment.active = point
        self.experiment.refresh()
        if point is not None:
            self.objects.set_selection(("sensor", -1))

    def set_interaction_locked(self, locked):
        self.locked = bool(locked)
        if locked:
            self._path_stage = None
            if self.objects.selection and self.objects.selection[0] == "magnet":
                self.objects.set_selection(None)
        self.path.line.setOpacity(0.6 if locked else 1.0)
        self.path.points.setOpacity(0.5 if locked else 1.0)

    def set_manual_point_creation_enabled(self, enabled):
        self._manual_tool = bool(enabled)
        self.experiment.preview.hide()

    def cancel_action(self):
        self.set_path_creation_enabled(False)
        self.set_manual_point_creation_enabled(False)
        self.pathCreationFinished.emit()
        self.actionCancelled.emit()

    def projected_experiment_point(self, x, y):
        point = project_to_segment(self.scene.path, x, y) if self.scene else None
        if point is not None and self._screen_distance(x, y, point[1], point[2]) <= 12:
            return point
        return None

    def reset_view(self) -> None:
        self.view_box.setRange(xRange=(-80, 80), yRange=(-50, 50), padding=0)
        self._view_changed()

    def zoom_in(self) -> None:
        self.view_box.scaleBy((0.8, 0.8))

    def zoom_out(self) -> None:
        self.view_box.scaleBy((1.25, 1.25))

    def set_zoom(self, factor: float) -> None:
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("zoom must be positive and finite")
        amount = self.zoom / factor
        self.view_box.scaleBy((amount, amount))

    @property
    def zoom(self) -> float:
        xmin, xmax = self.view_box.viewRange()[0]
        # Reference the fitted physical domain at the current widget aspect ratio.
        # Resizing the window alone must not register as a user zoom operation.
        fitted_width = max(
            160.0, 100.0 * self.view_box.width() / max(1.0, self.view_box.height())
        )
        return fitted_width / max(xmax - xmin, 1e-12)

    def _viewport_origin(self):
        return QPointF(
            self.graphics.viewport().mapTo(
                self, self.graphics.viewport().rect().topLeft()
            )
        )

    def screen_to_world(self, pos_px: QPointF) -> tuple[float, float]:
        """Input is a position in FieldCanvas coordinates, in logical pixels."""
        viewport_pos = QPointF(pos_px) - self._viewport_origin()
        inverse, ok = self.graphics.viewportTransform().inverted()
        if not ok:
            raise ValueError("View transform is not invertible")
        point = self.view_box.mapSceneToView(inverse.map(viewport_pos))
        return float(point.x()), float(point.y())

    def world_to_screen(self, x_mm: float, y_mm: float) -> QPointF:
        point = self.view_box.mapViewToScene(QPointF(x_mm, y_mm))
        return self.graphics.viewportTransform().map(point) + self._viewport_origin()

    def _screen_distance(self, x, y, px, py):
        a, b = self.world_to_screen(x, y), self.world_to_screen(px, py)
        return math.hypot(a.x() - b.x(), a.y() - b.y())

    def hit_test(self, x_mm: float, y_mm: float):
        return self.path.hit_test(
            x_mm, y_mm, self._screen_distance
        ) or self.objects.hit_test(x_mm, y_mm, self._screen_distance)

    def _view_changed(self, *args):
        ranges = self.view_box.viewRange()
        self.empty_label.setPos(
            (ranges[0][0] + ranges[0][1]) / 2, (ranges[1][0] + ranges[1][1]) / 2
        )
        pixels = max(1.0, self.view_box.width())
        desired = (ranges[0][1] - ranges[0][0]) * 85 / pixels
        decade = 10 ** math.floor(math.log10(max(desired, 1e-9)))
        size = min((1, 2, 5, 10), key=lambda v: abs(v * decade - desired)) * decade
        self.scale_bar.size = size
        self.scale_bar.text.setText(f"{size:g} мм")
        self.scale_bar.updateBar()
        self.viewTransformChanged.emit(self.zoom)

    def _event_world(self, event):
        return self.screen_to_world(event.position() + self._viewport_origin())

    def _tooltip(self, hit):
        if hit is None or self.scene is None:
            return ""
        kind, identifier = hit
        if kind.startswith("magnet"):
            m = next((m for m in self.scene.magnets if m.id == identifier), None)
            return (
                ""
                if m is None
                else f"Магнит {m.id}\nX = {m.x_mm:.1f} мм\nY = {m.y_mm:.1f} мм\nS → N = {m.angle_deg:.1f}°"
            )
        if kind.startswith("sensor"):
            s = self.scene.sensor
            return f"Датчик Холла\nX = {s.x_mm:.1f} мм\nY = {s.y_mm:.1f} мм\nЧувствительная ось = {s.angle_deg:.1f}°"
        p = self.scene.path
        x, y = (p.ax_mm, p.ay_mm) if identifier == "A" else (p.bx_mm, p.by_mm)
        return f"Точка {identifier}\nX = {x:.1f} мм\nY = {y:.1f} мм"

    def eventFilter(self, watched, event):
        if watched is not self.graphics.viewport():
            return super().eventFilter(watched, event)
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            self.setFocus()
            x, y = self._event_world(event)
            if event.button() == Qt.MouseButton.MiddleButton:
                self._pan = (event.position(), deepcopy(self.view_box.viewRange()))
                watched.setCursor(Qt.CursorShape.ClosedHandCursor)
                return True
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            if self._manual_tool:
                point = self.projected_experiment_point(x, y)
                if point is not None:
                    self.set_manual_point_creation_enabled(False)
                    self.experimentPointRequested.emit(*point)
                return True
            if self.mode is AppSection.EXPERIMENT:
                sensor_hit = self.objects.hit_test(x, y, self._screen_distance)
                selected = self.experiment.hit_test(x, y, self._screen_distance)
                if selected is not None and (
                    sensor_hit is None or sensor_hit[0] != "sensor_rotation"
                ):
                    self.experimentPointSelected.emit(selected)
                    return True
            if self._path_stage is not None:
                point = self._path_stage
                self._path_stage = "B" if point == "A" else None
                self.pathPointMoved.emit(
                    point, float(np.clip(x, -80, 80)), float(np.clip(y, -50, 50))
                )
                if point == "B":
                    watched.setCursor(Qt.CursorShape.ArrowCursor)
                    self.pathCreationFinished.emit()
                return True
            self._active = self.hit_test(x, y)
            if self._active is None:
                self.objects.set_selection(None)
                self.objectSelected.emit("none", -1)
                return True
            target, identifier = self._active
            if (
                (self.locked and (target.startswith("magnet") or target == "path"))
                or (target == "sensor" and not self.sensor_translation_enabled)
                or (target == "sensor_rotation" and not self.sensor_rotation_enabled)
            ):
                if target == "sensor":
                    self.objects.set_selection(("sensor", -1))
                else:
                    self.interactionBlocked.emit()
                self._active = None
                return True
            selection = (target.replace("_rotation", ""), identifier)
            if target != "path":
                self.objects.set_selection(selection)
                self.objectSelected.emit(*selection)
            self.set_interaction_quality("drag")
            if target == "magnet":
                m = next(m for m in self.scene.magnets if m.id == identifier)
                self._offset = (m.x_mm - x, m.y_mm - y)
                self.magnetDragStarted.emit(identifier)
            elif target == "sensor":
                s = self.scene.sensor
                self._offset = (s.x_mm - x, s.y_mm - y)
                self.sensorDragStarted.emit()
            elif target == "magnet_rotation":
                self.magnetRotationStarted.emit(identifier)
            self._last_position = (x, y)
            return True
        if kind == QEvent.Type.MouseMove:
            x, y = self._event_world(event)
            self.cursorWorldPositionChanged.emit(x, y)
            if self._manual_tool:
                projected = self.projected_experiment_point(x, y)
                self.experiment.preview.setVisible(projected is not None)
                if projected:
                    self.experiment.preview.setData([projected[1]], [projected[2]])
            if self._pan is not None:
                origin, ranges = self._pan
                delta = event.position() - origin
                dx = (
                    -delta.x()
                    * (ranges[0][1] - ranges[0][0])
                    / max(1, self.view_box.width())
                )
                dy = (
                    delta.y()
                    * (ranges[1][1] - ranges[1][0])
                    / max(1, self.view_box.height())
                )
                self.view_box.setRange(
                    xRange=(ranges[0][0] + dx, ranges[0][1] + dx),
                    yRange=(ranges[1][0] + dy, ranges[1][1] + dy),
                    padding=0,
                )
                return True
            if self._active is not None:
                self._move_active(x, y)
                return True
            hit = self.hit_test(x, y)
            watched.setToolTip(self._tooltip(hit))
            cursor = (
                Qt.CursorShape.CrossCursor
                if self._path_stage is not None or self._manual_tool
                else (
                    Qt.CursorShape.OpenHandCursor if hit else Qt.CursorShape.ArrowCursor
                )
            )
            watched.setCursor(cursor)
        if kind == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.MiddleButton and self._pan is not None:
                self._pan = None
                watched.setCursor(Qt.CursorShape.ArrowCursor)
                return True
            if event.button() == Qt.MouseButton.LeftButton and self._active is not None:
                self._move_active(*self._event_world(event))
                target, identifier = self._active
                x, y = self._last_position
                if target == "magnet":
                    self.magnetDragFinished.emit(identifier, x, y)
                elif target == "sensor":
                    self.sensorDragFinished.emit(x, y)
                elif target == "magnet_rotation":
                    self.magnetRotationFinished.emit(identifier, x)
                self._active = None
                self.set_interaction_quality("full")
                return True
        return super().eventFilter(watched, event)

    def _move_active(self, x, y):
        target, identifier = self._active
        if target in {"magnet", "sensor"}:
            x = float(np.clip(x + self._offset[0], -80, 80))
            y = float(np.clip(y + self._offset[1], -50, 50))
            self._last_position = (x, y)
            if target == "magnet":
                self.magnetDragged.emit(identifier, x, y)
            else:
                self.sensorDragged.emit(x, y)
        elif target == "path":
            x, y = float(np.clip(x, -80, 80)), float(np.clip(y, -50, 50))
            self._last_position = (x, y)
            self.pathPointMoved.emit(identifier, x, y)
        else:
            if target == "magnet_rotation":
                m = next(m for m in self.scene.magnets if m.id == identifier)
                angle = (math.degrees(math.atan2(y - m.y_mm, x - m.x_mm)) - 90) % 360
                self.magnetRotated.emit(identifier, angle)
            else:
                s = self.scene.sensor
                angle = math.degrees(math.atan2(y - s.y_mm, x - s.x_mm)) % 360
                self.sensorRotated.emit(angle)
            self._last_position = (angle, 0.0)

    def shutdown(self):
        """Drain the visualization worker before destroying the Qt view."""
        self.streamlines.shutdown()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)
