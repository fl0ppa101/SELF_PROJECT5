"""Standalone visual sandbox: python -m hallsim.visualization.demo.

The controls here are a test harness for visualization, not the production GUI.
"""
import argparse
from pathlib import Path
import sys
import time
import numpy as np
from PyQt6.QtCore import QSignalBlocker, QTimer, Qt
from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout,
                            QFrame, QHBoxLayout, QLabel, QPushButton, QSplitter,
                            QScrollArea, QVBoxLayout, QWidget)
from hallsim.core.enums import ColorRangeMode, FieldNormalization, SensorOrientationMode
from .field_canvas import FieldCanvas
from .mock_data import mock_grid, mock_profile, mock_reading, mock_scene
from .path_plot import PathProfilePlot
from .theme import stylesheet


def _title(text):
    label = QLabel(text)
    label.setObjectName("heading")
    return label


def _card(title):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(12)
    layout.addWidget(_title(title))
    return frame, layout


class DemoWindow(QWidget):
    def __init__(self, theme="light", scenario="single_magnet", show_path=False):
        super().__init__()
        self.setWindowTitle("HallSim · Визуализация")
        self.resize(1280, 920)
        self.scene = mock_scene(scenario)
        self.scene.path.enabled = show_path
        self.theme_name = theme
        self.selected = ("sensor", -1)
        self._last_grid_time = 0.
        self._pending_grid = False
        self.grid_timer = QTimer(self)
        self.grid_timer.setSingleShot(True)
        self.grid_timer.timeout.connect(self._flush_drag)
        main = QVBoxLayout(self)
        main.setContentsMargins(18, 14, 18, 10)
        main.setSpacing(14)
        top = QHBoxLayout()
        brand = QLabel("∿  HallSim")
        brand.setStyleSheet("font: bold 28px 'Georgia'; background: transparent;")
        top.addWidget(brand)
        top.addSpacing(28)
        top.addWidget(_title("Визуализация · XY"))
        top.addStretch()
        badge = QLabel("Демонстрационные данные")
        badge.setObjectName("muted")
        top.addWidget(badge)
        self.theme_button = QPushButton("Тёмная тема" if theme == "light" else "Светлая тема")
        self.theme_button.clicked.connect(self.toggle_theme)
        top.addWidget(self.theme_button)
        main.addLayout(top)
        body = QHBoxLayout()
        body.setSpacing(16)
        splitter = QSplitter(Qt.Orientation.Vertical)
        map_card, map_layout = _card("2D поле магнитов")
        map_toolbar = QHBoxLayout()
        hint = QLabel("Колесо — масштаб · Средняя кнопка — перемещение · R — сброс")
        hint.setObjectName("muted")
        map_toolbar.addWidget(hint)
        map_toolbar.addStretch()
        for title, method in [("−", "zoom_out"), ("+", "zoom_in"), ("Сброс", "reset_view")]:
            button = QPushButton(title)
            button.setFixedHeight(30)
            map_toolbar.addWidget(button)
            button.clicked.connect(lambda _, m=method: getattr(self.canvas, m)())
        map_layout.addLayout(map_toolbar)
        self.canvas = FieldCanvas()
        map_layout.addWidget(self.canvas, 1)
        self.path_button = QPushButton("Задать путь A–B")
        self.path_button.setCheckable(True)
        self.path_button.toggled.connect(self.canvas.set_path_creation_enabled)
        map_bottom = QHBoxLayout()
        map_bottom.addWidget(self.path_button)
        hide_path = QPushButton("Убрать путь")
        hide_path.clicked.connect(self.clear_path)
        map_bottom.addWidget(hide_path)
        map_bottom.addStretch()
        self.align_button = QPushButton("Выровнять по полю")
        self.align_button.clicked.connect(self.align_sensor)
        map_bottom.addWidget(self.align_button)
        map_layout.addLayout(map_bottom)
        splitter.addWidget(map_card)
        graph_card, graph_layout = _card("Модуль магнитной индукции вдоль пути A–B")
        self.path_plot = PathProfilePlot()
        graph_layout.addWidget(self.path_plot)
        graph_footer = QHBoxLayout()
        self.profile_info = QLabel("Задайте две точки на карте")
        self.profile_info.setObjectName("muted")
        graph_footer.addWidget(self.profile_info)
        graph_footer.addStretch()
        self.graph_scale = QComboBox()
        self.graph_scale.addItems(["Linear", "Log"])
        self.graph_scale.currentTextChanged.connect(self.path_plot.set_y_scale)
        graph_footer.addWidget(self.graph_scale)
        graph_layout.addLayout(graph_footer)
        splitter.addWidget(graph_card)
        splitter.setSizes([630, 250])
        splitter.setCollapsible(0, False)
        body.addWidget(splitter, 1)
        sidebar_widget = QWidget()
        sidebar = QVBoxLayout(sidebar_widget)
        sidebar.setContentsMargins(0, 0, 0, 0)
        sidebar.setSpacing(14)
        view_card, view_layout = _card("Параметры визуализации")
        view_card.setFixedWidth(300)
        self.layer_boxes = {}
        for label, field in [("Тепловая карта |B|", "show_heatmap"), ("Линии поля", "show_field_lines"), ("Сетка координат", "show_grid")]:
            checkbox = QCheckBox(label)
            checkbox.setChecked(getattr(self.scene.view, field))
            checkbox.toggled.connect(lambda checked, f=field: self.change_view(f, checked))
            self.layer_boxes[field] = checkbox
            view_layout.addWidget(checkbox)
        form = QFormLayout()
        form.setSpacing(10)
        self.normalization = QComboBox()
        self.normalization.addItems(["Power", "Linear", "Log"])
        self.normalization.currentTextChanged.connect(lambda v: self.change_view("normalization", FieldNormalization[v.upper()]))
        form.addRow("Нормализация", self.normalization)
        self.range_mode = QComboBox()
        self.range_mode.addItems(["Авто 99.5%", "Авто полный", "Вручную"])
        self.range_mode.currentIndexChanged.connect(self.change_range)
        form.addRow("Диапазон", self.range_mode)
        self.palette_combo = QComboBox()
        self.palette_combo.addItems(["Hall", "Viridis", "Turbo"])
        self.palette_combo.currentTextChanged.connect(self.canvas.set_palette)
        form.addRow("Палитра", self.palette_combo)
        self.manual_min = self._spin(0., 1e6, .1)
        self.manual_max = self._spin(.001, 1e6, .1)
        self.manual_max.setValue(50.)
        self.manual_min.valueChanged.connect(self.change_manual_range)
        self.manual_max.valueChanged.connect(self.change_manual_range)
        form.addRow("Минимум, мТл", self.manual_min)
        form.addRow("Максимум, мТл", self.manual_max)
        self.manual_min.setEnabled(False)
        self.manual_max.setEnabled(False)
        view_layout.addLayout(form)
        self.view_message = QLabel("")
        self.view_message.setWordWrap(True)
        self.view_message.setObjectName("muted")
        view_layout.addWidget(self.view_message)
        sidebar.addWidget(view_card)
        scene_card, scene_layout = _card("Сцена для проверки")
        scene_card.setFixedWidth(300)
        self.scenario_combo = QComboBox()
        self.scenario_combo.addItems(["Один магнит", "Два магнита · N–N", "Два магнита · N–S"])
        self.scenario_combo.setCurrentIndex(["single_magnet", "like_poles", "opposite_poles"].index(scenario))
        self.scenario_combo.currentIndexChanged.connect(self.change_scenario)
        scene_layout.addWidget(self.scenario_combo)
        self.object_combo = QComboBox()
        self.object_combo.currentIndexChanged.connect(self.select_from_combo)
        scene_layout.addWidget(self.object_combo)
        object_form = QFormLayout()
        self.x_spin = self._spin(-80, 80, 1.)
        self.y_spin = self._spin(-50, 50, 1.)
        self.angle_spin = self._spin(0, 359.99, 5.)
        for label, spin in [("X, мм", self.x_spin), ("Y, мм", self.y_spin), ("Угол, °", self.angle_spin)]:
            object_form.addRow(label, spin)
            spin.valueChanged.connect(self.edit_selected)
        scene_layout.addLayout(object_form)
        self.sensor_info = QLabel("")
        self.sensor_info.setWordWrap(True)
        self.sensor_info.setObjectName("muted")
        scene_layout.addWidget(self.sensor_info)
        sidebar.addWidget(scene_card)
        notes_card, notes_layout = _card("Управление на карте")
        notes_card.setFixedWidth(300)
        notes = QLabel("Перетащите магнит или датчик за корпус.\n\nВыберите объект и потяните круглый маркер для поворота.\n\nТочки A и B можно перемещать мышью.")
        notes.setWordWrap(True)
        notes.setObjectName("muted")
        notes_layout.addWidget(notes)
        sidebar.addWidget(notes_card)
        sidebar.addStretch()
        sidebar_scroll = QScrollArea()
        sidebar_scroll.setWidgetResizable(True)
        sidebar_scroll.setFixedWidth(318)
        sidebar_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sidebar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sidebar_scroll.setWidget(sidebar_widget)
        body.addWidget(sidebar_scroll)
        main.addLayout(body, 1)
        self.status = QLabel("Готово · Координаты: мм · Режим: 2D")
        self.status.setObjectName("muted")
        main.addWidget(self.status)
        self.canvas.magnetDragged.connect(self.drag_magnet)
        self.canvas.magnetDragFinished.connect(self.finish_magnet)
        self.canvas.magnetRotated.connect(self.rotate_magnet)
        self.canvas.magnetRotationFinished.connect(lambda *_: self.update_grid("full"))
        self.canvas.sensorDragged.connect(self.drag_sensor)
        self.canvas.sensorDragFinished.connect(lambda *_: self.update_sensor())
        self.canvas.sensorRotated.connect(self.rotate_sensor)
        self.canvas.pathPointMoved.connect(self.move_path)
        self.canvas.pathCreationFinished.connect(lambda: self.path_button.setChecked(False))
        self.canvas.objectSelected.connect(self.select_object)
        self.canvas.cursorWorldPositionChanged.connect(self.cursor_status)
        self.canvas.visualizationError.connect(lambda text: self.status.setText(text))
        self.refresh_objects()
        self.apply_theme()
        self.update_grid("full")

    @staticmethod
    def _spin(minimum, maximum, step):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(step)
        spin.setKeyboardTracking(False)
        return spin

    def apply_theme(self):
        self.setStyleSheet(stylesheet(self.theme_name))
        self.canvas.set_theme(self.theme_name)
        self.path_plot.set_theme(self.theme_name)
        self.theme_button.setText("Тёмная тема" if self.theme_name == "light" else "Светлая тема")

    def toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.apply_theme()

    def change_view(self, field, value):
        previous = getattr(self.scene.view, field)
        setattr(self.scene.view, field, value)
        try:
            self.canvas.set_scene(self.scene)
            self.view_message.setText("")
        except ValueError as exc:
            setattr(self.scene.view, field, previous)
            self.view_message.setText(str(exc))

    def change_range(self, index):
        manual = index == 2
        self.manual_min.setEnabled(manual)
        self.manual_max.setEnabled(manual)
        if manual:
            self.scene.view.color_min_mT = self.manual_min.value()
            self.scene.view.color_max_mT = self.manual_max.value()
            if self.scene.view.normalization == FieldNormalization.LOG and self.manual_min.value() == 0:
                self.manual_min.setValue(.001)
                self.scene.view.color_min_mT = .001
        self.change_view("color_range_mode", list(ColorRangeMode)[index])

    def change_manual_range(self, *_):
        if self.range_mode.currentIndex() != 2:
            return
        lo, hi = self.manual_min.value(), self.manual_max.value()
        if hi <= lo or (self.scene.view.normalization == FieldNormalization.LOG and lo <= 0):
            self.view_message.setText("Максимум должен быть больше минимума; для Log минимум > 0.")
            return
        self.scene.view.color_min_mT, self.scene.view.color_max_mT = lo, hi
        self.canvas.set_scene(self.scene)
        self.view_message.setText("")

    def change_scenario(self, index):
        view = self.scene.view
        self.scene = mock_scene(["single_magnet", "like_poles", "opposite_poles"][index])
        self.scene.view = view
        self.path_button.setChecked(False)
        self.refresh_objects()
        self.update_grid("full")

    def refresh_objects(self):
        blocker = QSignalBlocker(self.object_combo)
        self.object_combo.clear()
        for m in self.scene.magnets:
            self.object_combo.addItem(f"Магнит {m.id}", ("magnet", m.id))
        self.object_combo.addItem("Датчик Холла", ("sensor", -1))
        self.selected = ("sensor", -1)
        self.object_combo.setCurrentIndex(self.object_combo.count()-1)
        del blocker
        self.sync_controls()

    def selected_state(self):
        return self.scene.sensor if self.selected[0] == "sensor" else next(m for m in self.scene.magnets if m.id == self.selected[1])

    def sync_controls(self):
        state = self.selected_state()
        blockers = [QSignalBlocker(w) for w in (self.x_spin, self.y_spin, self.angle_spin)]
        self.x_spin.setValue(state.x_mm)
        self.y_spin.setValue(state.y_mm)
        self.angle_spin.setValue(state.angle_deg)
        del blockers

    def select_from_combo(self, index):
        if index >= 0:
            self.selected = self.object_combo.itemData(index)
            self.canvas.objects.set_selection(self.selected)
            self.sync_controls()

    def select_object(self, kind, identifier):
        if kind not in {"sensor", "magnet"}:
            return
        self.selected = (kind, identifier)
        blocker = QSignalBlocker(self.object_combo)
        for i in range(self.object_combo.count()):
            if self.object_combo.itemData(i) == self.selected:
                self.object_combo.setCurrentIndex(i)
        del blocker
        self.sync_controls()

    def edit_selected(self, *_):
        state = self.selected_state()
        angle_changed = abs(state.angle_deg - self.angle_spin.value()) > .011
        state.x_mm, state.y_mm, state.angle_deg = self.x_spin.value(), self.y_spin.value(), self.angle_spin.value()
        self.scene.revision += 1
        if self.selected[0] == "sensor":
            if angle_changed:
                state.orientation_mode = SensorOrientationMode.MANUAL
            self.update_sensor()
        else:
            self.update_grid("full")

    def update_grid(self, quality):
        self.grid_timer.stop()
        self._pending_grid = False
        self.grid = mock_grid(self.scene, quality)
        self._last_grid_time = time.monotonic()
        self.canvas.set_scene(self.scene)
        self.canvas.set_field_grid(self.grid)
        self.update_sensor()
        self.update_profile()

    def schedule_grid(self):
        self.canvas.set_scene(self.scene)
        self._pending_grid = True
        if not self.grid_timer.isActive():
            remaining = max(0, 1/30 - (time.monotonic()-self._last_grid_time))
            self.grid_timer.start(int(remaining*1000)+1)

    def _flush_drag(self):
        if self._pending_grid:
            self.update_grid("drag")

    def drag_magnet(self, mid, x, y):
        m = next(m for m in self.scene.magnets if m.id == mid)
        m.x_mm, m.y_mm = x, y
        self.scene.revision += 1
        self.schedule_grid()
        self.sync_controls()

    def finish_magnet(self, mid, x, y):
        self.drag_magnet(mid, x, y)
        self.update_grid("full")

    def rotate_magnet(self, mid, angle):
        next(m for m in self.scene.magnets if m.id == mid).angle_deg = angle
        self.scene.revision += 1
        self.schedule_grid()
        self.sync_controls()

    def drag_sensor(self, x, y):
        self.scene.sensor.x_mm, self.scene.sensor.y_mm = x, y
        self.scene.revision += 1
        self.update_sensor()
        self.sync_controls()

    def rotate_sensor(self, angle):
        self.scene.sensor.angle_deg = angle
        self.scene.sensor.orientation_mode = SensorOrientationMode.MANUAL
        self.scene.revision += 1
        self.update_sensor()
        self.sync_controls()

    def update_sensor(self):
        reading = mock_reading(self.grid, self.scene.sensor)
        if self.scene.sensor.orientation_mode == SensorOrientationMode.AUTO and reading.field.direction_deg is not None:
            self.scene.sensor.angle_deg = reading.field.direction_deg
        self.canvas.set_scene(self.scene)
        self.canvas.set_sensor_reading(reading)
        value = f"{reading.value_mT:.2f} мТл" if np.isfinite(reading.value_mT) else "не определено"
        self.sensor_info.setText(f"Датчик: {self.scene.sensor.orientation_mode.name}\nЗначение из тестовой сетки: {value}")
        self.sync_controls()

    def align_sensor(self):
        self.scene.sensor.orientation_mode = SensorOrientationMode.AUTO
        self.update_sensor()
        self.sync_controls()

    def move_path(self, point, x, y):
        p = self.scene.path
        if self.canvas._path_stage == "B" and point == "A":
            p.bx_mm, p.by_mm = x, y
        p.enabled = True
        if point == "A":
            p.ax_mm, p.ay_mm = x, y
        else:
            p.bx_mm, p.by_mm = x, y
        self.scene.revision += 1
        self.canvas.set_scene(self.scene)
        self.update_profile()

    def clear_path(self):
        self.scene.path.enabled = False
        self.scene.revision += 1
        self.path_button.setChecked(False)
        self.canvas.set_scene(self.scene)
        self.update_profile()

    def update_profile(self):
        profile = mock_profile(self.grid, self.scene.path, self.scene.revision)
        self.path_plot.set_profile(profile)
        if profile is None:
            self.profile_info.setText("Задайте две разные точки на карте")
        else:
            valid = profile.modB_mT[profile.valid_mask]
            text = f"A → B: {profile.distance_mm[-1]:.1f} мм"
            if len(valid):
                text += f"   ·   min {valid.min():.2f}   max {valid.max():.2f} мТл"
            self.profile_info.setText(text)

    def cursor_status(self, x, y):
        self.status.setText(f"X = {x:.1f} мм     Y = {y:.1f} мм     ·     Масштаб {self.canvas.zoom*100:.0f}%     ·     2D")

    def closeEvent(self, event):
        self.grid_timer.stop()
        self.canvas.shutdown()
        super().closeEvent(event)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Standalone HallSim visualization demo, synthetic data only")
    parser.add_argument("--theme", choices=["light", "dark"], default="light")
    parser.add_argument("--scenario", choices=["single_magnet", "like_poles", "opposite_poles"], default="single_magnet")
    parser.add_argument("--path", action="store_true", help="Enable a horizontal A–B demonstration path")
    parser.add_argument("--screenshot", type=Path, help="Capture this widget after streamline rendering and exit")
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("HallSim Visualization Demo")
    window = DemoWindow(args.theme, args.scenario, args.path)
    window.show()
    if args.screenshot:
        captured = False
        def capture():
            nonlocal captured
            if captured:
                return
            captured = True
            args.screenshot.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(args.screenshot)):
                raise RuntimeError("Unable to save preview")
            print(f"Preview: {args.screenshot.resolve()}")
            window.close()
            app.quit()
        window.canvas.streamlines.updated.connect(lambda: QTimer.singleShot(200, capture))
        QTimer.singleShot(20000, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
