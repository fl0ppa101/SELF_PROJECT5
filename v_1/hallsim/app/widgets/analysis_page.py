from __future__ import annotations

from math import hypot

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

from hallsim.app.config import MAX_PATH_SAMPLES, MIN_PATH_SAMPLES, X_MAX_MM, X_MIN_MM, Y_MAX_MM, Y_MIN_MM
from hallsim.core.contracts import SceneState

from ..visualization_bridge import create_path_profile_plot


def _coordinate_spin(minimum: float, maximum: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(minimum, maximum)
    spin.setDecimals(1)
    spin.setSuffix(" мм")
    spin.setKeyboardTracking(False)
    return spin


class AnalysisPage(QWidget):
    pathEnabledChanged = pyqtSignal(bool)
    pathPointEdited = pyqtSignal(str, float, float)
    pathSamplesEdited = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Анализ поля")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Профиль модуля магнитной индукции вдоль прямого пути A-B")
        subtitle.setObjectName("pageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)
        self.path_enabled = QCheckBox("Путь A-B включён")
        self.path_enabled.toggled.connect(self.pathEnabledChanged)
        header.addWidget(self.path_enabled)
        root.addLayout(header)

        controls = QFrame()
        controls.setObjectName("contentCard")
        controls_layout = QGridLayout(controls)
        controls_layout.setContentsMargins(16, 14, 16, 14)
        controls_layout.setHorizontalSpacing(10)
        controls_layout.setVerticalSpacing(9)

        self.ax = _coordinate_spin(X_MIN_MM, X_MAX_MM)
        self.ay = _coordinate_spin(Y_MIN_MM, Y_MAX_MM)
        self.bx = _coordinate_spin(X_MIN_MM, X_MAX_MM)
        self.by = _coordinate_spin(Y_MIN_MM, Y_MAX_MM)
        self.samples = QSpinBox()
        self.samples.setRange(MIN_PATH_SAMPLES, MAX_PATH_SAMPLES)
        self.samples.setSuffix(" точек")
        self.samples.setKeyboardTracking(False)
        self.distance_label = QLabel("— мм")
        self.distance_label.setObjectName("metricValue")

        controls_layout.addWidget(QLabel("Точка A"), 0, 0)
        controls_layout.addWidget(QLabel("X"), 0, 1)
        controls_layout.addWidget(self.ax, 0, 2)
        controls_layout.addWidget(QLabel("Y"), 0, 3)
        controls_layout.addWidget(self.ay, 0, 4)
        controls_layout.addWidget(QLabel("Точка B"), 1, 0)
        controls_layout.addWidget(QLabel("X"), 1, 1)
        controls_layout.addWidget(self.bx, 1, 2)
        controls_layout.addWidget(QLabel("Y"), 1, 3)
        controls_layout.addWidget(self.by, 1, 4)
        controls_layout.addWidget(QLabel("Длина A-B"), 0, 5)
        controls_layout.addWidget(self.distance_label, 0, 6)
        controls_layout.addWidget(QLabel("Дискретизация"), 1, 5)
        controls_layout.addWidget(self.samples, 1, 6)
        root.addWidget(controls)

        plot_card = QFrame()
        plot_card.setObjectName("contentCard")
        plot_layout = QVBoxLayout(plot_card)
        plot_layout.setContentsMargins(14, 12, 14, 14)
        plot_header = QHBoxLayout()
        plot_title = QLabel("|B|(s)")
        plot_title.setObjectName("contentTitle")
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["Linear", "Log"])
        self.reset_plot_button = QPushButton("Сбросить масштаб")
        self.reset_plot_button.setObjectName("secondaryButton")
        plot_header.addWidget(plot_title)
        plot_header.addStretch(1)
        plot_header.addWidget(QLabel("Шкала Y"))
        plot_header.addWidget(self.scale_combo)
        plot_header.addWidget(self.reset_plot_button)
        plot_layout.addLayout(plot_header)
        self.path_plot = create_path_profile_plot(plot_card)
        plot_layout.addWidget(self.path_plot, 1)
        root.addWidget(plot_card, 1)

        hint = QLabel(
            "NaN и недопустимые участки отображаются разрывом линии. "
            "Логарифмическая шкала включается только вручную."
        )
        hint.setObjectName("pageSubtitle")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.ax.editingFinished.connect(lambda: self._emit_point("A"))
        self.ay.editingFinished.connect(lambda: self._emit_point("A"))
        self.bx.editingFinished.connect(lambda: self._emit_point("B"))
        self.by.editingFinished.connect(lambda: self._emit_point("B"))
        self.samples.editingFinished.connect(lambda: self.pathSamplesEdited.emit(self.samples.value()))
        self.scale_combo.currentTextChanged.connect(
            lambda text: self.path_plot.set_y_scale(text.lower())
        )
        if hasattr(self.path_plot, "reset_view"):
            self.reset_plot_button.clicked.connect(self.path_plot.reset_view)
        else:
            self.reset_plot_button.setEnabled(False)

    def _emit_point(self, point: str) -> None:
        if point == "A":
            self.pathPointEdited.emit("A", self.ax.value(), self.ay.value())
        else:
            self.pathPointEdited.emit("B", self.bx.value(), self.by.value())

    def refresh(self, scene: SceneState) -> None:
        path = scene.path
        widgets = [self.path_enabled, self.ax, self.ay, self.bx, self.by, self.samples]
        blockers = [QSignalBlocker(widget) for widget in widgets]
        self.path_enabled.setChecked(path.enabled)
        self.ax.setValue(path.ax_mm)
        self.ay.setValue(path.ay_mm)
        self.bx.setValue(path.bx_mm)
        self.by.setValue(path.by_mm)
        self.samples.setValue(path.samples)
        del blockers
        for widget in (self.ax, self.ay, self.bx, self.by, self.samples):
            widget.setEnabled(path.enabled)
        distance = hypot(path.bx_mm - path.ax_mm, path.by_mm - path.ay_mm)
        self.distance_label.setText(f"{distance:.1f} мм")
        if not path.enabled:
            self.path_plot.clear_with_message("Включите путь A-B для построения графика")

    def set_profile(self, profile) -> None:
        self.path_plot.set_profile(profile)

    def set_theme(self, theme: str) -> None:
        self.path_plot.set_theme(theme)

