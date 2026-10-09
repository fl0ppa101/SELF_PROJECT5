"""Laboratory widgets delegate state changes and measurements to controllers."""

import math
from PyQt6.QtCore import Qt, QSignalBlocker
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QScrollArea,
    QPushButton,
    QLabel,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)
from hallsim.core.enums import AppSection, MeasurementSource, SensorStudyAxis
from hallsim.visualization.field_canvas import FieldCanvas
from hallsim.visualization.experiment_layer import project_to_segment
from hallsim.visualization.lab_plots import ExperimentPlot, SensorStudyPlot
from .control_panel import ControlPanel, SectionFrame
from .custom_magnet_dialog import CustomMagnetDialog


def spin(minimum, maximum, value, suffix="", decimals=2):
    widget = QDoubleSpinBox()
    widget.setDecimals(decimals)
    widget.setRange(minimum, maximum)
    widget.setValue(value)
    widget.setSuffix(suffix)
    widget.setKeyboardTracking(False)
    return widget


def number(value, unit=""):
    return (
        f"{value:.5g} {unit}".strip()
        if value is not None and math.isfinite(value)
        else "Недопустимая точка"
    )


class LabPage(QWidget):
    def __init__(self, controller, mode, parent=None):
        super().__init__(parent)
        self.controller, self.mode = controller, mode
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        left = QWidget()
        area = QVBoxLayout(left)
        area.setContentsMargins(0, 0, 8, 0)
        heading = QLabel(
            "Виртуальная лаборатория"
            if mode is AppSection.EXPERIMENT
            else "Исследование датчика Холла"
        )
        heading.setObjectName("contentTitle")
        area.addWidget(heading)
        self.canvas = FieldCanvas()
        self.canvas.set_mode(mode)
        area.addWidget(self.canvas, 1)
        toolbar = QHBoxLayout()
        if mode is AppSection.EXPERIMENT:
            self.path_button = QPushButton("Задать путь A–B")
            self.path_button.setCheckable(True)
            self.manual_button = QPushButton("Добавить ручную точку")
            self.manual_button.setCheckable(True)
            toolbar.addWidget(self.path_button)
            toolbar.addWidget(self.manual_button)
            self.path_button.toggled.connect(self.canvas.set_path_creation_enabled)
            self.manual_button.toggled.connect(
                self.canvas.set_manual_point_creation_enabled
            )
            self.path_button.toggled.connect(
                lambda checked: (
                    self.manual_button.setChecked(False) if checked else None
                )
            )
            self.manual_button.toggled.connect(
                lambda checked: self.path_button.setChecked(False) if checked else None
            )
            self.canvas.pathCreationFinished.connect(
                lambda: self.path_button.setChecked(False)
            )
            self.canvas.experimentPointRequested.connect(self._request_manual)
            self.canvas.experimentPointSelected.connect(
                lambda s: self.safe(controller.select_point, s)
            )
            self.canvas.interactionBlocked.connect(controller.blocked)
            self.canvas.actionCancelled.connect(self._escape)
        toolbar.addStretch(1)
        for label, action in [
            ("−", self.canvas.zoom_out),
            ("+", self.canvas.zoom_in),
            ("Сбросить вид", self.canvas.reset_view),
        ]:
            button = QPushButton(label)
            button.clicked.connect(action)
            toolbar.addWidget(button)
        area.addLayout(toolbar)
        self.plot = (
            ExperimentPlot() if mode is AppSection.EXPERIMENT else SensorStudyPlot()
        )
        self.plot.setMaximumHeight(245)
        area.addWidget(self.plot)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("pageSubtitle")
        area.addWidget(self.status)
        self.cursor = QLabel("Координаты: мм · Напряжение: мВ")
        area.addWidget(self.cursor)
        self.canvas.cursorWorldPositionChanged.connect(self._cursor)
        split.addWidget(left)
        self.panel = ControlPanel()
        self.panel.layers_section.hide()
        self.panel.sensor_section.hide()
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(6, 0, 6, 0)
        if mode is AppSection.EXPERIMENT:
            self._experiment_controls(side, area)
        else:
            self._study_controls(side)
        side.addWidget(self.panel)
        side.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(sidebar)
        scroll.setMinimumWidth(440)
        scroll.setMaximumWidth(480)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        split.addWidget(scroll)
        split.setStretchFactor(0, 1)
        split.setSizes([940, 450])
        root.addWidget(split)
        self._connect_scene()
        controller.changed.connect(self.refresh)
        if mode is AppSection.EXPERIMENT:
            controller.message.connect(self.status.setText)
        else:
            controller.curveChanged.connect(self.plot.set_curve)
        self.panel.set_catalog(controller.scene_controller.magnet_definitions())
        self._table_signature = None
        self.refresh()

    def safe(self, callback, *args, **kwargs):
        try:
            callback(*args, **kwargs)
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))

    def edit(self, method, *args, **kwargs):
        self.safe(self.controller.edit_scene, method, *args, **kwargs)

    def _connect_scene(self):
        c = self.canvas
        p = self.panel
        for signal, method in [
            (p.magnetPositionEdited, "set_magnet_position"),
            (c.magnetDragged, "set_magnet_position"),
            (c.magnetDragFinished, "set_magnet_position"),
            (p.magnetAngleEdited, "set_magnet_angle"),
            (c.magnetRotated, "set_magnet_angle"),
            (c.magnetRotationFinished, "set_magnet_angle"),
            (p.magnetDefinitionEdited, "set_magnet_definition"),
            (p.magnetEnabledEdited, "set_magnet_enabled"),
            (p.removeMagnetRequested, "remove_magnet"),
            (p.addMagnetRequested, "add_magnet"),
            (p.presetRequested, "apply_preset"),
        ]:
            signal.connect(lambda *args, m=method: self.edit(m, *args))
        # clicked(bool) is not a scene argument.
        p.customMagnetRequested.connect(self._custom)
        if self.mode is AppSection.EXPERIMENT:
            c.pathPointMoved.connect(
                lambda point, x, y: self.edit("set_path_point", point, x, y)
            )
            c.sensorRotated.connect(
                lambda angle: self.safe(self.controller.rotate_sensor, angle)
            )
        else:
            c.sensorDragged.connect(lambda x, y: self.edit("set_sensor_position", x, y))
            c.sensorDragFinished.connect(
                lambda x, y: self.edit("set_sensor_position", x, y)
            )
            c.sensorRotated.connect(lambda angle: self.edit("set_sensor_angle", angle))

    def _custom(self):
        if self.mode is AppSection.EXPERIMENT and self.controller.state.locked:
            self.controller.blocked()
            return
        dialog = CustomMagnetDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        def create():
            identifier = self.controller.scene_controller.create_custom_magnet(
                dialog.name_edit.text(), dialog.moment_spin.value()
            )
            self.edit(
                "set_magnet_definition",
                self.controller.scene().magnets[0].id,
                identifier,
            )

        self.safe(create)

    def _experiment_controls(self, side, area):
        setup = SectionFrame("Эксперимент")
        self.lock_label = QLabel("Установка готова к настройке")
        setup.layout_box.addWidget(self.lock_label)
        self.reset_button = QPushButton("Начать заново")
        self.reset_button.clicked.connect(self._reset)
        setup.layout_box.addWidget(self.reset_button)
        self.path_info = QLabel()
        self.path_info.setWordWrap(True)
        setup.layout_box.addWidget(self.path_info)
        form = QFormLayout()
        self.count = QSpinBox()
        self.count.setRange(2, 200)
        self.count.setValue(50)
        self.step = spin(1, 180, 10, "°", 1)
        form.addRow("Количество точек N", self.count)
        form.addRow("Шаг поворота Δα", self.step)
        setup.layout_box.addLayout(form)
        self.auto_button = QPushButton("Провести автоматическое измерение")
        self.auto_button.setObjectName("primaryButton")
        self.auto_button.clicked.connect(self._automatic)
        setup.layout_box.addWidget(self.auto_button)
        self.progress = QProgressBar()
        self.progress.setRange(0, 50)
        self.progress.setFormat("Измерение: %v / %m")
        setup.layout_box.addWidget(self.progress)
        side.addWidget(setup)
        instrument = SectionFrame("Датчик Холла — виртуальный прибор")
        self.sensor_position = QLabel()
        self.voltage = QLabel("Выберите ручную точку на A–B")
        self.voltage.setObjectName("sensorReading")
        self.voltage.setWordWrap(True)
        self.sensor_angle = spin(0, 359.9, 0, "°", 1)
        self.sensor_angle.editingFinished.connect(
            lambda: self.safe(self.controller.rotate_sensor, self.sensor_angle.value())
        )
        instrument.layout_box.addWidget(self.sensor_position)
        angle = QFormLayout()
        angle.addRow("Угол чувствительной оси", self.sensor_angle)
        instrument.layout_box.addLayout(angle)
        instrument.layout_box.addWidget(self.voltage)
        p = self.controller.state.sensor_params
        instrument.layout_box.addWidget(
            QLabel(
                f"I = {p.current_mA:g} мА · d = {p.thickness_mm:g} мм\nR_H = {p.hall_coefficient_m3_C:g} м³/Кл"
            )
        )
        self.capture_info = QLabel("Снято измерений: 0")
        instrument.layout_box.addWidget(self.capture_info)
        self.capture_button = QPushButton("Снять измерение")
        self.finish_button = QPushButton("Завершить точку")
        self.cancel_button = QPushButton("Отменить точку")
        for button, action in [
            (self.capture_button, self.controller.capture),
            (self.finish_button, self.controller.finish_manual_point),
            (self.cancel_button, self.controller.cancel_manual_point),
        ]:
            button.clicked.connect(lambda checked=False, fn=action: self.safe(fn))
            instrument.layout_box.addWidget(button)
        side.addWidget(instrument)
        self.compare_button = QPushButton("Сравнить с теорией")
        self.compare_button.clicked.connect(lambda: self.safe(self.controller.compare))
        side.addWidget(self.compare_button)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        side.addWidget(self.error_label)
        self.table_toggle = QPushButton("Показать таблицу измерений")
        self.table_toggle.setCheckable(True)
        area.addWidget(self.table_toggle)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["№", "s, мм", "x, мм", "y, мм", "|U_H|max, мВ", "|B|изм, мТл", "Источник"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setMinimumHeight(130)
        self.table.setMaximumHeight(220)
        self.table.hide()
        area.addWidget(self.table)
        self.table_toggle.toggled.connect(self.table.setVisible)

    def _study_controls(self, side):
        frame = SectionFrame("Параметры датчика Холла")
        form = QFormLayout()
        self.current = spin(0, 100, 10, " мА", 3)
        self.thickness = spin(0.0001, 10, 0.2, " мм", 4)
        self.coefficient = spin(-1, 1, 0.001, " м³/Кл", 8)
        self.coefficient.setSingleStep(0.0001)
        self.sensor_x = spin(-80, 80, 0, " мм", 2)
        self.sensor_y = spin(-50, 50, 30, " мм", 2)
        self.sensor_angle = spin(0, 359.9, 0, "°", 1)
        for name, control in [
            ("Ток I", self.current),
            ("Толщина d", self.thickness),
            ("Коэффициент R_H", self.coefficient),
            ("X", self.sensor_x),
            ("Y", self.sensor_y),
            ("Угол α", self.sensor_angle),
        ]:
            form.addRow(name, control)
        frame.layout_box.addLayout(form)
        for control in (self.current, self.thickness, self.coefficient):
            control.editingFinished.connect(
                lambda: self.safe(
                    self.controller.set_parameters,
                    self.current.value(),
                    self.thickness.value(),
                    self.coefficient.value(),
                )
            )
        for control in (self.sensor_x, self.sensor_y):
            control.editingFinished.connect(
                lambda: self.edit(
                    "set_sensor_position", self.sensor_x.value(), self.sensor_y.value()
                )
            )
        self.sensor_angle.editingFinished.connect(
            lambda: self.edit("set_sensor_angle", self.sensor_angle.value())
        )
        self.axis = QComboBox()
        for name, value in [
            ("U_H(I)", SensorStudyAxis.CURRENT),
            ("U_H(d)", SensorStudyAxis.THICKNESS),
            ("U_H(α)", SensorStudyAxis.ANGLE),
        ]:
            self.axis.addItem(name, value)
        self.axis.currentIndexChanged.connect(
            lambda: self.safe(self.controller.set_axis, self.axis.currentData())
        )
        frame.layout_box.addWidget(self.axis)
        self.voltage = QLabel()
        self.voltage.setObjectName("sensorReading")
        self.field_info = QLabel()
        self.field_info.setWordWrap(True)
        frame.layout_box.addWidget(self.voltage)
        frame.layout_box.addWidget(self.field_info)
        side.addWidget(frame)

    def _request_manual(self, s, x, y):
        self.manual_button.setChecked(False)
        self.safe(self.controller.activate_manual_point, s, x, y)

    def _escape(self):
        self.manual_button.setChecked(False)
        if self.controller.active is not None:
            self.controller.cancel_manual_point()

    def _reset(self):
        if self.controller.state.points:
            answer = QMessageBox.question(
                self,
                "Начать заново",
                "Текущие результаты измерений будут удалены. Продолжить?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.canvas.cancel_action()
        self.controller.reset()

    def _automatic(self):
        def start():
            self.controller.set_config(self.count.value(), self.step.value())
            self.controller.start_automatic()

        self.safe(start)

    def refresh(self):
        c = self.controller
        scene = c.scene()
        self.panel.refresh(scene)
        self.canvas.set_scene(scene)
        blocker = QSignalBlocker(self.sensor_angle)
        self.sensor_angle.setValue(scene.sensor.angle_deg)
        del blocker
        if self.mode is AppSection.EXPERIMENT:
            locked = c.state.locked
            self.canvas.set_interaction_locked(locked)
            self.canvas.sensor_translation_enabled = False
            self.canvas.sensor_rotation_enabled = c.active is not None and not c.running
            self.canvas.set_experiment_points(c.state.points)
            self.canvas.set_experiment_pending_points(c.pending)
            self.canvas.set_active_experiment_point(c.active)
            self.panel.magnets_section.setEnabled(not locked)
            self.panel.presets_section.setEnabled(not locked)
            self.path_button.setEnabled(not locked)
            self.manual_button.setEnabled(
                scene.path.enabled and not c.running and c.active is None
            )
            self.lock_label.setText(
                "Установка зафиксирована"
                if locked
                else "Настройте магниты и отрезок A–B"
            )
            p = scene.path
            self.path_info.setText(
                f"A: ({p.ax_mm:.1f}; {p.ay_mm:.1f}) мм\nB: ({p.bx_mm:.1f}; {p.by_mm:.1f}) мм\nДлина: {math.hypot(p.bx_mm-p.ax_mm,p.by_mm-p.ay_mm):.2f} мм"
                if p.enabled
                else "Задайте отрезок A–B на карте"
            )
            self.sensor_position.setText(
                f"X = {scene.sensor.x_mm:.2f} мм · Y = {scene.sensor.y_mm:.2f} мм"
            )
            self.sensor_angle.setEnabled(c.active is not None and not c.running)
            self.voltage.setText(
                "U_H = " + number(c.reading.hall_voltage_mV, "мВ")
                if c.reading
                else "Выберите ручную точку на A–B"
            )
            self.capture_info.setText(f"Снято измерений: {len(c.captures)}")
            self.capture_button.setEnabled(c.active is not None and not c.running)
            self.finish_button.setEnabled(bool(c.captures) and not c.running)
            self.cancel_button.setEnabled(c.active is not None)
            self.auto_button.setEnabled(
                not c.running and c.active is None and p.enabled
            )
            self.compare_button.setEnabled(bool(c.state.points) and not c.running)
            self.count.setEnabled(not c.running)
            self.step.setEnabled(not c.running)
            completed, total = c.progress
            self.progress.setRange(0, max(1, total))
            self.progress.setValue(completed)
            self.progress.setVisible(total > 0)
            self.plot.set_measurements(c.state.points)
            self.plot.set_comparison(c.comparison)
            self.error_label.setText(
                "Среднее абсолютное отклонение: "
                + number(c.comparison.mean_abs_error_mT, "мТл")
                if c.comparison
                else ""
            )
            signature = tuple(c.state.points)
            if signature != self._table_signature:
                self._table_signature = signature
                self.table.setRowCount(len(signature))
                for row, p in enumerate(signature):
                    source = (
                        "ручной"
                        if p.source is MeasurementSource.MANUAL
                        else "автоматический"
                    )
                    values = [
                        str(row + 1),
                        number(p.s_mm),
                        number(p.x_mm),
                        number(p.y_mm),
                        number(p.max_abs_hall_voltage_mV),
                        number(p.measured_modB_mT),
                        source,
                    ]
                    for col, value in enumerate(values):
                        self.table.setItem(row, col, QTableWidgetItem(value))
        else:
            params = c.state.sensor_params
            for widget, value in [
                (self.sensor_x, scene.sensor.x_mm),
                (self.sensor_y, scene.sensor.y_mm),
                (self.current, params.current_mA),
                (self.thickness, params.thickness_mm),
                (self.coefficient, params.hall_coefficient_m3_C),
            ]:
                blocker = QSignalBlocker(widget)
                widget.setValue(value)
                del blocker
            blocker = QSignalBlocker(self.axis)
            self.axis.setCurrentIndex(self.axis.findData(c.state.selected_axis))
            del blocker
            r = c.reading
            self.voltage.setText("U_H = " + number(r.hall_voltage_mV, "мВ"))
            f = r.field
            self.field_info.setText(
                f'Bx = {number(f.bx_mT,"мТл")}\nBy = {number(f.by_mT,"мТл")}\n|B| = {number(f.modB_mT,"мТл")}\nB_s = {number(r.sensitive_component_mT,"мТл")}'
            )

    def _cursor(self, x, y):
        text = f"X = {x:.1f} мм · Y = {y:.1f} мм"
        if self.mode is AppSection.EXPERIMENT:
            projected = project_to_segment(self.controller.state.path, x, y)
            if projected:
                text += f" · s = {projected[0]:.2f} мм"
        else:
            text += (
                " · |B| = "
                + number(self.controller.field.modB_mT, "мТл")
                + " · U_H = "
                + number(self.controller.reading.hall_voltage_mV, "мВ")
            )
        self.cursor.setText(text + f" · Масштаб {self.canvas.zoom*100:.0f}%")

    def set_theme(self, theme):
        self.canvas.set_theme(theme)
        self.plot.set_theme(theme)
