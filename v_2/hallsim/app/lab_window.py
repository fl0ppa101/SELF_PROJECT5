from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QPushButton,
    QLabel,
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
)
from hallsim.core.enums import AppSection
from .main_window import MainWindow as VisualizationWindow
from .widgets.lab_page import LabPage
from .widgets.theme_switch import AnimatedThemeSwitch


class MainWindow(QMainWindow):
    def __init__(
        self,
        visual_controller,
        experiment_controller,
        study_controller,
        settings_service,
    ):
        super().__init__()
        self.visual_controller = visual_controller
        self.experiment_controller = experiment_controller
        self.study_controller = study_controller
        self.settings_service = settings_service
        self.setWindowTitle("HallSim — виртуальная лаборатория")
        self.resize(1440, 960)
        self.setMinimumSize(1160, 780)
        geometry = settings_service.restore_window_geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QWidget()
        bar.setObjectName("topBar")
        nav = QHBoxLayout(bar)
        nav.setContentsMargins(18, 10, 18, 10)
        logo = QLabel("∿  HallSim")
        logo.setObjectName("logoLabel")
        nav.addWidget(logo)
        self.buttons = []
        for index, title in enumerate(
            ("Визуализация", "Эксперимент", "Исследование датчика")
        ):
            button = QPushButton(title)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self.set_section(i))
            nav.addWidget(button)
            self.buttons.append(button)
        nav.addStretch(1)
        settings = QPushButton("Настройки")
        settings.clicked.connect(self.show_settings)
        nav.addWidget(settings)
        help_button = QPushButton("Справка")
        help_button.clicked.connect(self.show_help)
        nav.addWidget(help_button)
        self.theme_switch = AnimatedThemeSwitch()
        self.theme_switch.themeRequested.connect(visual_controller.set_theme)
        nav.addWidget(self.theme_switch)
        layout.addWidget(bar)
        self.pages = QStackedWidget()
        self.visualization = VisualizationWindow(visual_controller)
        self.visualization.setParent(self, Qt.WindowType.Widget)
        self.visualization.setMinimumSize(0, 0)
        self.visualization.centralWidget().layout().itemAt(0).widget().hide()
        self.experiment = LabPage(experiment_controller, AppSection.EXPERIMENT)
        self.study = LabPage(study_controller, AppSection.SENSOR_STUDY)
        for page in (self.visualization, self.experiment, self.study):
            self.pages.addWidget(page)
        layout.addWidget(self.pages, 1)
        self.setCentralWidget(central)
        self.settings_dialog = None
        self.help_dialog = None
        visual_controller.themeChanged.connect(self.set_theme)
        visual_controller.catalogChanged.connect(self._catalog_changed)
        for scene_controller in (
            experiment_controller.scene_controller,
            study_controller.scene_controller,
        ):
            scene_controller.catalogChanged.connect(self._catalog_changed)
        s = self.visualization.settings_page
        s.visualizationPresetChanged.connect(visual_controller.set_visualization_preset)
        s.paletteChanged.connect(visual_controller.set_palette)
        s.lineDensityChanged.connect(visual_controller.set_line_density)
        self.set_theme(visual_controller.theme)
        sections = list(AppSection)
        self.set_section(sections.index(visual_controller.app_settings().last_section))
        self.settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self.settings_shortcut.activated.connect(self.show_settings)

    def _catalog_changed(self, catalog):
        if hasattr(self.visual_controller._calculation_service, "update_catalog"):
            self.visual_controller._calculation_service.update_catalog(catalog)
            self.visual_controller._request_calculation(
                self.visual_controller.scene(), "full", "all"
            )
        if not getattr(self.experiment_controller.engine, "is_mock", False):
            from hallsim.physics.engine import PhysicsEngine

            engine = PhysicsEngine(catalog)
            self.experiment_controller.engine = engine
            self.study_controller.engine = engine
        for ctrl, panel in [
            (self.visual_controller, self.visualization.control_panel),
            (self.experiment_controller.scene_controller, self.experiment.panel),
            (self.study_controller.scene_controller, self.study.panel),
        ]:
            ctrl._catalog = dict(catalog)
            panel.set_catalog(catalog)
        self.study_controller.refresh()

    def set_section(self, index):
        self.pages.setCurrentIndex(index)
        self.visualization._switch_page(0)
        self.visual_controller._app_settings.last_section = list(AppSection)[index]
        for i, button in enumerate(self.buttons):
            button.setChecked(i == index)

    def set_theme(self, theme):
        path = (
            Path(__file__).resolve().parents[1] / "resources" / "qss" / f"{theme}.qss"
        )
        self.setStyleSheet(
            path.read_text(encoding="utf-8").replace(
                "@RESOURCE_DIR@", path.parents[1].as_posix()
            )
        )
        self.experiment.set_theme(theme)
        self.study.set_theme(theme)
        self.theme_switch.set_theme(theme)

    def show_settings(self):
        if self.settings_dialog is None:
            self.settings_dialog = QDialog(self)
            self.settings_dialog.setWindowTitle("Настройки — Визуализация")
            self.settings_dialog.resize(760, 760)
            layout = QVBoxLayout(self.settings_dialog)
            page = self.visualization.settings_page
            self.visualization.page_stack.removeWidget(page)
            layout.addWidget(page)
            close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            close.rejected.connect(self.settings_dialog.close)
            layout.addWidget(close)
        self.settings_dialog.show()
        self.settings_dialog.raise_()

    def show_help(self):
        if self.help_dialog is None:
            self.help_dialog = QDialog(self)
            self.help_dialog.setWindowTitle("HallSim — краткая справка")
            self.help_dialog.resize(700, 560)
            layout = QVBoxLayout(self.help_dialog)
            text = QTextBrowser()
            text.setHtml(
                "<h2>Виртуальная лаборатория HallSim</h2><p><b>Визуализация:</b> перемещайте магниты и датчик, включайте карту и линии поля. В настройках доступны режимы «Наглядный», «Линейный» и «Пользовательский».</p><p><b>Эксперимент:</b> задайте A–B, затем проведите автоматическое измерение или добавьте ручную точку. В ручной точке вращайте датчик, снимайте значения U_H и завершите точку. Установка фиксируется до «Начать заново». Точное поле скрыто; теория появится после «Сравнить с теорией».</p><p><b>Исследование датчика:</b> меняйте I, d, R_H и угол. Выбирайте график U_H(I), U_H(d) или U_H(α). Изменения не влияют на эксперимент.</p><p>Левая кнопка — выбор и перемещение; ручка — вращение; колесо — масштаб; средняя кнопка — камера; R — сброс вида; Esc — отмена выбора точек.</p><p>Единицы: мм, °, мТл, мА, мВ. Датчик измеряет знаковую компоненту поля. Используется учебная модель точечных диполей и идеального эффекта Холла.</p>"
            )
            layout.addWidget(text)
        self.help_dialog.show()
        self.help_dialog.raise_()

    def shutdown(self):
        self.experiment_controller.shutdown()
        self.study_controller.timer.stop()
        self.visual_controller.shutdown()
        for canvas in (
            self.visualization.canvas,
            self.experiment.canvas,
            self.study.canvas,
        ):
            canvas.shutdown()

    def closeEvent(self, event):
        self.shutdown()
        self.settings_service.save(
            self.visual_controller.app_settings(),
            self.visual_controller.scene(),
            self.saveGeometry(),
        )
        super().closeEvent(event)
