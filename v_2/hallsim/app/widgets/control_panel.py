from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from hallsim.app.config import MAX_GUI_MAGNETS, X_MAX_MM, X_MIN_MM, Y_MAX_MM, Y_MIN_MM
from hallsim.core.contracts import MagnetState, SceneState
from hallsim.core.enums import SensorOrientationMode
from hallsim.core.magnet_catalog import MAGNET_CATALOG


def _coordinate_spin(minimum: float, maximum: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(1)
    spin.setSingleStep(1.0)
    spin.setSuffix(" мм")
    spin.setKeyboardTracking(False)
    return spin


class SectionFrame(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sectionFrame")
        self.layout_box = QVBoxLayout(self)
        self.layout_box.setContentsMargins(12, 10, 12, 12)
        self.layout_box.setSpacing(9)
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        self.layout_box.addWidget(label)


class MagnetCard(QFrame):
    positionEdited = pyqtSignal(int, float, float)
    angleEdited = pyqtSignal(int, float)
    definitionEdited = pyqtSignal(int, str)
    enabledEdited = pyqtSignal(int, bool)
    removeRequested = pyqtSignal(int)

    def __init__(
        self, magnet: MagnetState, parent: QWidget | None = None, *, definitions=None
    ) -> None:
        super().__init__(parent)
        self.magnet_id = magnet.id
        self._definitions = dict(MAGNET_CATALOG if definitions is None else definitions)
        self.setObjectName("magnetCard")
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        self.enabled = QCheckBox()
        self.enabled.setToolTip("Показывать и учитывать магнит")
        self.title = QLabel()
        self.title.setObjectName("cardTitle")
        self.remove_button = QPushButton("Удалить")
        self.remove_button.setObjectName("flatDangerButton")
        self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        header.addWidget(self.enabled)
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.remove_button)
        root.addLayout(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)
        self.definition = QComboBox()
        self.definition.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.definition.setMinimumContentsLength(18)
        for definition in self._definitions.values():
            self.definition.addItem(definition.display_name, definition.id)
        self.x_spin = _coordinate_spin(X_MIN_MM, X_MAX_MM)
        self.y_spin = _coordinate_spin(Y_MIN_MM, Y_MAX_MM)
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(0.0, 359.9)
        self.angle_spin.setDecimals(1)
        self.angle_spin.setSuffix("°")
        self.angle_spin.setKeyboardTracking(False)

        grid.addWidget(QLabel("Тип"), 0, 0)
        grid.addWidget(self.definition, 0, 1, 1, 3)
        grid.addWidget(QLabel("X"), 1, 0)
        grid.addWidget(self.x_spin, 1, 1)
        grid.addWidget(QLabel("Y"), 1, 2)
        grid.addWidget(self.y_spin, 1, 3)
        grid.addWidget(QLabel("Угол S→N"), 2, 0, 1, 2)
        grid.addWidget(self.angle_spin, 2, 2, 1, 2)
        root.addLayout(grid)

        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setObjectName("pageSubtitle")
        root.addWidget(self.details)

        self.enabled.toggled.connect(
            lambda checked: self.enabledEdited.emit(self.magnet_id, checked)
        )
        self.remove_button.clicked.connect(
            lambda: self.removeRequested.emit(self.magnet_id)
        )
        self.definition.currentIndexChanged.connect(self._emit_definition)
        self.x_spin.editingFinished.connect(self._emit_position)
        self.y_spin.editingFinished.connect(self._emit_position)
        self.angle_spin.editingFinished.connect(
            lambda: self.angleEdited.emit(self.magnet_id, self.angle_spin.value())
        )
        self.refresh(magnet)

    def _emit_position(self) -> None:
        self.positionEdited.emit(
            self.magnet_id, self.x_spin.value(), self.y_spin.value()
        )

    def _emit_definition(self) -> None:
        definition_id = self.definition.currentData()
        if definition_id is not None:
            self.definitionEdited.emit(self.magnet_id, str(definition_id))

    def refresh(self, magnet: MagnetState) -> None:
        blockers = [
            QSignalBlocker(self.enabled),
            QSignalBlocker(self.definition),
            QSignalBlocker(self.x_spin),
            QSignalBlocker(self.y_spin),
            QSignalBlocker(self.angle_spin),
        ]
        self.title.setText(f"Магнит {magnet.id}")
        self.enabled.setChecked(magnet.enabled)
        index = self.definition.findData(magnet.definition_id)
        self.definition.setCurrentIndex(max(index, 0))
        self.x_spin.setValue(magnet.x_mm)
        self.y_spin.setValue(magnet.y_mm)
        self.angle_spin.setValue(magnet.angle_deg)
        definition = self._definitions.get(magnet.definition_id)
        if definition is not None:
            metadata = [
                value for value in (definition.material, definition.grade) if value
            ]
            metadata.append(f"{definition.moment_Am2:.4g} А·м²")
            self.details.setText(" · ".join(metadata))
        del blockers


class ControlPanel(QWidget):
    layerChanged = pyqtSignal(str, bool)
    addMagnetRequested = pyqtSignal()
    magnetPositionEdited = pyqtSignal(int, float, float)
    magnetAngleEdited = pyqtSignal(int, float)
    magnetDefinitionEdited = pyqtSignal(int, str)
    magnetEnabledEdited = pyqtSignal(int, bool)
    removeMagnetRequested = pyqtSignal(int)
    sensorPositionEdited = pyqtSignal(float, float)
    sensorAngleEdited = pyqtSignal(float)
    sensorModeEdited = pyqtSignal(object)
    alignSensorRequested = pyqtSignal()
    presetRequested = pyqtSignal(str)
    customMagnetRequested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: dict[int, MagnetCard] = {}
        self._definitions = dict(MAGNET_CATALOG)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        title = QLabel("Параметры")
        title.setObjectName("panelTitle")
        root.addWidget(title)

        layers = SectionFrame("Слои")
        self.layers_section = layers
        self.heatmap_check = QCheckBox("Тепловая карта |B|")
        self.lines_check = QCheckBox("Линии поля")
        self.grid_check = QCheckBox("Сетка координат")
        for widget, key in (
            (self.heatmap_check, "heatmap"),
            (self.lines_check, "field_lines"),
            (self.grid_check, "grid"),
        ):
            widget.toggled.connect(
                lambda checked, layer=key: self.layerChanged.emit(layer, checked)
            )
            layers.layout_box.addWidget(widget)
        root.addWidget(layers)

        self.magnets_section = SectionFrame("Магниты")
        self.add_button = QPushButton("＋  Добавить магнит")
        self.add_button.setObjectName("secondaryButton")
        self.add_button.clicked.connect(self.addMagnetRequested)
        self.magnets_section.layout_box.addWidget(self.add_button)
        self.custom_button = QPushButton("Создать тип магнита")
        self.custom_button.setObjectName("secondaryButton")
        self.custom_button.clicked.connect(self.customMagnetRequested)
        self.magnets_section.layout_box.addWidget(self.custom_button)
        root.addWidget(self.magnets_section)

        sensor = SectionFrame("Датчик Холла")
        self.sensor_section = sensor
        grid = QGridLayout()
        self.sensor_x = _coordinate_spin(X_MIN_MM, X_MAX_MM)
        self.sensor_y = _coordinate_spin(Y_MIN_MM, Y_MAX_MM)
        self.sensor_angle = QDoubleSpinBox()
        self.sensor_angle.setRange(0.0, 359.9)
        self.sensor_angle.setDecimals(1)
        self.sensor_angle.setSuffix("°")
        self.sensor_angle.setKeyboardTracking(False)
        self.sensor_mode = QComboBox()
        self.sensor_mode.addItem("Автоматически", SensorOrientationMode.AUTO)
        self.sensor_mode.addItem("Вручную", SensorOrientationMode.MANUAL)
        self.sensor_reading = QLabel("— мТл")
        self.sensor_reading.setObjectName("sensorReading")
        grid.addWidget(QLabel("X"), 0, 0)
        grid.addWidget(self.sensor_x, 0, 1)
        grid.addWidget(QLabel("Y"), 0, 2)
        grid.addWidget(self.sensor_y, 0, 3)
        grid.addWidget(QLabel("Угол оси"), 1, 0, 1, 2)
        grid.addWidget(self.sensor_angle, 1, 2, 1, 2)
        grid.addWidget(QLabel("Режим"), 2, 0)
        grid.addWidget(self.sensor_mode, 2, 1, 1, 3)
        grid.addWidget(QLabel("Показание"), 3, 0, 1, 2)
        grid.addWidget(self.sensor_reading, 3, 2, 1, 2)
        sensor.layout_box.addLayout(grid)
        align = QPushButton("Выровнять по полю")
        align.setObjectName("primaryButton")
        align.clicked.connect(self.alignSensorRequested)
        sensor.layout_box.addWidget(align)
        self.sensor_x.editingFinished.connect(self._emit_sensor_position)
        self.sensor_y.editingFinished.connect(self._emit_sensor_position)
        self.sensor_angle.editingFinished.connect(
            lambda: self.sensorAngleEdited.emit(self.sensor_angle.value())
        )
        self.sensor_mode.currentIndexChanged.connect(self._emit_sensor_mode)
        root.addWidget(sensor)

        presets = SectionFrame("Пресеты")
        self.presets_section = presets
        for title_text, preset_id in (
            ("Один магнит", "single_magnet"),
            ("Одноимённые полюса", "like_poles"),
            ("Разноимённые полюса", "opposite_poles"),
        ):
            button = QPushButton(title_text)
            button.setObjectName("presetButton")
            button.clicked.connect(
                lambda checked=False, key=preset_id: self.presetRequested.emit(key)
            )
            presets.layout_box.addWidget(button)
        root.addWidget(presets)
        root.addStretch(1)

    def _emit_sensor_position(self) -> None:
        self.sensorPositionEdited.emit(self.sensor_x.value(), self.sensor_y.value())

    def _emit_sensor_mode(self) -> None:
        mode = self.sensor_mode.currentData()
        if mode is not None:
            self.sensorModeEdited.emit(mode)

    def _connect_card(self, card: MagnetCard) -> None:
        card.positionEdited.connect(self.magnetPositionEdited)
        card.angleEdited.connect(self.magnetAngleEdited)
        card.definitionEdited.connect(self.magnetDefinitionEdited)
        card.enabledEdited.connect(self.magnetEnabledEdited)
        card.removeRequested.connect(self.removeMagnetRequested)

    def set_catalog(self, definitions):
        self._definitions = dict(definitions)
        for card in self._cards.values():
            card._definitions = dict(self._definitions)
            selected = card.definition.currentData()
            blocker = QSignalBlocker(card.definition)
            card.definition.clear()
            for definition in self._definitions.values():
                card.definition.addItem(definition.display_name, definition.id)
            card.definition.setCurrentIndex(max(0, card.definition.findData(selected)))
            del blocker

    def refresh(self, scene: SceneState) -> None:
        layer_widgets = [self.heatmap_check, self.lines_check, self.grid_check]
        blockers = [QSignalBlocker(widget) for widget in layer_widgets]
        self.heatmap_check.setChecked(scene.view.show_heatmap)
        self.lines_check.setChecked(scene.view.show_field_lines)
        self.grid_check.setChecked(scene.view.show_grid)
        del blockers

        existing_ids = set(self._cards)
        scene_ids = {magnet.id for magnet in scene.magnets}
        if existing_ids != scene_ids:
            for card in self._cards.values():
                self.magnets_section.layout_box.removeWidget(card)
                card.deleteLater()
            self._cards.clear()
            self.magnets_section.layout_box.removeWidget(self.add_button)
            for magnet in scene.magnets:
                card = MagnetCard(magnet, definitions=self._definitions)
                self._connect_card(card)
                self._cards[magnet.id] = card
                self.magnets_section.layout_box.addWidget(card)
            self.magnets_section.layout_box.addWidget(self.add_button)
        else:
            for magnet in scene.magnets:
                self._cards[magnet.id].refresh(magnet)
        self.add_button.setEnabled(len(scene.magnets) < MAX_GUI_MAGNETS)
        for card in self._cards.values():
            card.remove_button.setVisible(len(scene.magnets) > 1)

        sensor = scene.sensor
        controls = [self.sensor_x, self.sensor_y, self.sensor_angle, self.sensor_mode]
        blockers = [QSignalBlocker(widget) for widget in controls]
        self.sensor_x.setValue(sensor.x_mm)
        self.sensor_y.setValue(sensor.y_mm)
        self.sensor_angle.setValue(sensor.angle_deg)
        self.sensor_mode.setCurrentIndex(
            self.sensor_mode.findData(sensor.orientation_mode)
        )
        del blockers
