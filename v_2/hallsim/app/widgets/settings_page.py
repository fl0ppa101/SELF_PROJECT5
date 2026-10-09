from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from hallsim.core.contracts import AppSettings, SceneState
from hallsim.core.enums import ColorRangeMode, FieldNormalization, VisualizationPreset


class SettingsPage(QWidget):
    visualizationPresetChanged = pyqtSignal(object)
    paletteChanged = pyqtSignal(str)
    lineDensityChanged = pyqtSignal(float)
    normalizationChanged = pyqtSignal(object)
    colorRangeModeChanged = pyqtSignal(object)
    percentileChanged = pyqtSignal(float)
    gammaChanged = pyqtSignal(float)
    manualRangeChanged = pyqtSignal(float, float)
    saveLastSceneChanged = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("settingsContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title = QLabel("Настройки")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Отображение поля и поведение приложения")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        visual = QFrame()
        visual.setObjectName("contentCard")
        visual_box = QVBoxLayout(visual)
        visual_box.setContentsMargins(16, 14, 16, 16)
        visual_title = QLabel("Визуализация магнитного поля")
        visual_title.setObjectName("contentTitle")
        visual_box.addWidget(visual_title)
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(11)
        self.preset = QComboBox()
        for name, value in [
            ("Наглядный", VisualizationPreset.ILLUSTRATIVE),
            ("Линейный", VisualizationPreset.LINEAR),
            ("Пользовательский", VisualizationPreset.CUSTOM),
        ]:
            self.preset.addItem(name, value)
        self.palette = QComboBox()
        for name, value in [
            ("Hall", "hall"),
            ("Viridis", "viridis"),
            ("Turbo", "turbo"),
        ]:
            self.palette.addItem(name, value)
        self.density = QDoubleSpinBox()
        self.density.setRange(0.25, 2.0)
        self.density.setSingleStep(0.25)
        self.density.setKeyboardTracking(False)
        form.addRow("Режим отображения", self.preset)
        form.addRow("Палитра", self.palette)
        form.addRow("Плотность линий", self.density)
        self.preset.currentIndexChanged.connect(
            lambda: self.visualizationPresetChanged.emit(self.preset.currentData())
        )
        self.palette.currentIndexChanged.connect(
            lambda: self.paletteChanged.emit(self.palette.currentData())
        )
        self.density.editingFinished.connect(
            lambda: self.lineDensityChanged.emit(self.density.value())
        )
        self.normalization = QComboBox()
        self.normalization.addItem("Linear", FieldNormalization.LINEAR)
        self.normalization.addItem("Log", FieldNormalization.LOG)
        self.normalization.addItem("Power / Gamma", FieldNormalization.POWER)
        self.range_mode = QComboBox()
        self.range_mode.addItem("Auto percentile", ColorRangeMode.AUTO_PERCENTILE)
        self.range_mode.addItem("Auto full", ColorRangeMode.AUTO_FULL)
        self.range_mode.addItem("Manual", ColorRangeMode.MANUAL)
        self.percentile = QDoubleSpinBox()
        self.percentile.setRange(90.0, 100.0)
        self.percentile.setDecimals(1)
        self.percentile.setSuffix(" %")
        self.percentile.setKeyboardTracking(False)
        self.gamma = QDoubleSpinBox()
        self.gamma.setRange(0.05, 3.0)
        self.gamma.setDecimals(2)
        self.gamma.setSingleStep(0.05)
        self.gamma.setKeyboardTracking(False)
        manual_row = QHBoxLayout()
        self.color_min = QDoubleSpinBox()
        self.color_min.setRange(0.0, 1_000_000.0)
        self.color_min.setDecimals(3)
        self.color_min.setSuffix(" мТл")
        self.color_min.setKeyboardTracking(False)
        self.color_max = QDoubleSpinBox()
        self.color_max.setRange(0.0, 1_000_000.0)
        self.color_max.setDecimals(3)
        self.color_max.setSuffix(" мТл")
        self.color_max.setKeyboardTracking(False)
        manual_row.addWidget(QLabel("min"))
        manual_row.addWidget(self.color_min)
        manual_row.addWidget(QLabel("max"))
        manual_row.addWidget(self.color_max)
        form.addRow("Нормализация", self.normalization)
        form.addRow("Цветовой диапазон", self.range_mode)
        form.addRow("Верхний percentile", self.percentile)
        form.addRow("Gamma", self.gamma)
        form.addRow("Ручной диапазон", manual_row)
        visual_box.addLayout(form)
        info = QLabel(
            "Автоматический цветовой диапазон вычисляется по всей FieldGrid. "
            "Zoom и pan не меняют цвета."
        )
        info.setWordWrap(True)
        info.setObjectName("pageSubtitle")
        visual_box.addWidget(info)
        root.addWidget(visual)

        app_card = QFrame()
        app_card.setObjectName("contentCard")
        app_box = QVBoxLayout(app_card)
        app_box.setContentsMargins(16, 14, 16, 16)
        app_title = QLabel("Приложение")
        app_title.setObjectName("contentTitle")
        app_box.addWidget(app_title)
        self.save_last_scene = QCheckBox("Восстанавливать последнюю сцену при запуске")
        app_box.addWidget(self.save_last_scene)
        app_info = QLabel(
            "Тема, геометрия окна, zoom и простые параметры отображения сохраняются локально. "
            "Приложение работает без сети."
        )
        app_info.setWordWrap(True)
        app_info.setObjectName("pageSubtitle")
        app_box.addWidget(app_info)
        root.addWidget(app_card)

        limits = QFrame()
        limits.setObjectName("contentCard")
        limits_box = QVBoxLayout(limits)
        limits_box.setContentsMargins(16, 14, 16, 16)
        limits_title = QLabel("Параметры проекта")
        limits_title.setObjectName("contentTitle")
        limits_box.addWidget(limits_title)
        limits_box.addWidget(QLabel("Рабочая область: X −80…+80 мм, Y −50…+50 мм"))
        limits_box.addWidget(
            QLabel("Интерактивная сетка: 320×200; полная сетка: 640×400")
        )
        limits_box.addWidget(QLabel("Максимум магнитов в GUI: 2"))
        root.addWidget(limits)
        root.addStretch(1)
        scroll.setWidget(content)
        page_layout.addWidget(scroll)

        self.normalization.currentIndexChanged.connect(self._emit_normalization)
        self.range_mode.currentIndexChanged.connect(self._emit_range_mode)
        self.percentile.editingFinished.connect(
            lambda: self.percentileChanged.emit(self.percentile.value())
        )
        self.gamma.editingFinished.connect(
            lambda: self.gammaChanged.emit(self.gamma.value())
        )
        self.color_min.editingFinished.connect(self._emit_manual_range)
        self.color_max.editingFinished.connect(self._emit_manual_range)
        self.save_last_scene.toggled.connect(self.saveLastSceneChanged)

    def _emit_normalization(self) -> None:
        value = self.normalization.currentData()
        if value is not None:
            self.normalizationChanged.emit(value)
        self._update_enabled_state()

    def _emit_range_mode(self) -> None:
        value = self.range_mode.currentData()
        if value is not None:
            self.colorRangeModeChanged.emit(value)
        self._update_enabled_state()

    def _emit_manual_range(self) -> None:
        self.manualRangeChanged.emit(self.color_min.value(), self.color_max.value())

    def _update_enabled_state(self) -> None:
        custom = self.preset.currentData() is VisualizationPreset.CUSTOM
        mode = self.range_mode.currentData()
        self.normalization.setEnabled(custom)
        self.range_mode.setEnabled(custom)
        self.percentile.setEnabled(custom and mode is ColorRangeMode.AUTO_PERCENTILE)
        manual = custom and mode is ColorRangeMode.MANUAL
        self.color_min.setEnabled(manual)
        self.color_max.setEnabled(manual)
        self.gamma.setEnabled(
            custom and self.normalization.currentData() is FieldNormalization.POWER
        )

    def refresh(self, scene: SceneState, app_settings: AppSettings) -> None:
        view = scene.view
        widgets = [
            self.preset,
            self.palette,
            self.density,
            self.normalization,
            self.range_mode,
            self.percentile,
            self.gamma,
            self.color_min,
            self.color_max,
            self.save_last_scene,
        ]
        blockers = [QSignalBlocker(widget) for widget in widgets]
        self.preset.setCurrentIndex(self.preset.findData(view.preset))
        self.palette.setCurrentIndex(self.palette.findData(view.palette))
        self.density.setValue(view.line_density)
        self.normalization.setCurrentIndex(
            self.normalization.findData(view.normalization)
        )
        self.range_mode.setCurrentIndex(self.range_mode.findData(view.color_range_mode))
        self.percentile.setValue(view.percentile_clip)
        self.gamma.setValue(view.power_gamma)
        self.color_min.setValue(view.color_min_mT or 0.0)
        self.color_max.setValue(view.color_max_mT or 50.0)
        self.save_last_scene.setChecked(app_settings.save_last_scene)
        del blockers
        self._update_enabled_state()
