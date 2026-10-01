from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .controller import AppController
from .help_dialog import HelpDialog
from .settings_service import SettingsService
from .visualization_bridge import create_field_canvas, create_path_profile_plot
from .widgets import AnalysisPage, AnimatedThemeSwitch, ControlPanel, SettingsPage


class MainWindow(QMainWindow):
    def __init__(
        self,
        controller: AppController,
        settings_service: SettingsService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self._settings_service = settings_service
        self._current_theme: str | None = None
        self._theme_overlay: QLabel | None = None
        self._theme_fade = None
        self._help_dialog: HelpDialog | None = None
        self.setWindowTitle("HallSim")
        self.resize(1380, 900)
        self.setMinimumSize(1080, 700)
        if settings_service is not None:
            geometry = settings_service.restore_window_geometry()
            if geometry is not None:
                self.restoreGeometry(geometry)
        self._build_ui()
        self._connect_controller()
        self._install_shortcuts()
        self.controller.publish_initial_state()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_topbar())
        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self._build_modeling_page())
        self.analysis_page = AnalysisPage()
        self.settings_page = SettingsPage()
        self.page_stack.addWidget(self.analysis_page)
        self.page_stack.addWidget(self.settings_page)
        root.addWidget(self.page_stack, 1)

        self.setCentralWidget(central)
        self._build_statusbar()
        self._connect_controls()

    def _build_modeling_page(self) -> QWidget:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setObjectName("mainSplitter")
        main_splitter.setChildrenCollapsible(False)

        work_area = QWidget()
        work_layout = QVBoxLayout(work_area)
        work_layout.setContentsMargins(16, 14, 8, 12)
        work_layout.setSpacing(10)
        work_layout.addWidget(self._build_canvas_card(), 1)
        work_layout.addWidget(self._build_plot_card())
        main_splitter.addWidget(work_area)

        self.control_panel = ControlPanel()
        scroll = QScrollArea()
        scroll.setObjectName("sideScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.control_panel)
        scroll.setMinimumWidth(355)
        scroll.setMaximumWidth(430)
        main_splitter.addWidget(scroll)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 0)
        main_splitter.setSizes([1020, 380])
        page_layout.addWidget(main_splitter)
        return page

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(8)
        logo = QLabel("∿  HallSim")
        logo.setObjectName("logoLabel")
        layout.addWidget(logo)
        layout.addSpacing(28)
        self.nav_buttons: dict[int, QPushButton] = {}
        for index, title in enumerate(("Моделирование", "Анализ", "Настройки")):
            button = QPushButton(title)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setObjectName("navButton")
            button.clicked.connect(lambda checked=False, page=index: self._switch_page(page))
            self.nav_buttons[index] = button
            layout.addWidget(button)
        self.help_button = QPushButton("Справка")
        self.help_button.setObjectName("navButton")
        self.help_button.clicked.connect(self._show_help)
        layout.addWidget(self.help_button)
        layout.addStretch(1)
        self.theme_switch = AnimatedThemeSwitch()
        self.theme_switch.themeRequested.connect(self.controller.set_theme)
        layout.addWidget(self.theme_switch)
        return bar

    def _build_canvas_card(self) -> QWidget:
        card = QFrame()
        card.setObjectName("contentCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        toolbar = QHBoxLayout()
        title = QLabel("2D поле магнитов")
        title.setObjectName("contentTitle")
        toolbar.addWidget(title)
        toolbar.addStretch(1)
        view_label = QLabel("Вид:")
        self.view_combo = QComboBox()
        self.view_combo.addItem("Сверху (XY)")
        toolbar.addWidget(view_label)
        toolbar.addWidget(self.view_combo)
        layout.addLayout(toolbar)

        layers = QHBoxLayout()
        layers.addStretch(1)
        self.quick_heatmap = QCheckBox("Тепловая карта")
        self.quick_lines = QCheckBox("Линии поля")
        self.quick_grid = QCheckBox("Сетка")
        layers.addWidget(self.quick_heatmap)
        layers.addWidget(self.quick_lines)
        layers.addWidget(self.quick_grid)
        layout.addLayout(layers)

        self.canvas = create_field_canvas(card)
        layout.addWidget(self.canvas, 1)
        controls = QHBoxLayout()
        self.zoom_out = QPushButton("−")
        self.zoom_in = QPushButton("+")
        self.reset_view = QPushButton("Сбросить вид")
        for button in (self.zoom_out, self.zoom_in, self.reset_view):
            button.setObjectName("canvasButton")
        controls.addStretch(1)
        controls.addWidget(self.zoom_out)
        controls.addWidget(self.zoom_in)
        controls.addWidget(self.reset_view)
        layout.addLayout(controls)
        return card

    def _build_plot_card(self) -> QWidget:
        self.plot_card = QFrame()
        self.plot_card.setObjectName("contentCard")
        layout = QVBoxLayout(self.plot_card)
        layout.setContentsMargins(12, 8, 12, 10)
        header = QHBoxLayout()
        title = QLabel("Модуль магнитной индукции вдоль пути A-B")
        title.setObjectName("contentTitle")
        self.plot_scale = QComboBox()
        self.plot_scale.addItems(["Linear", "Log"])
        self.collapse_plot = QToolButton()
        self.collapse_plot.setText("Свернуть")
        self.collapse_plot.setCheckable(True)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.plot_scale)
        header.addWidget(self.collapse_plot)
        layout.addLayout(header)
        self.path_plot = create_path_profile_plot(self.plot_card)
        layout.addWidget(self.path_plot)
        self.collapse_plot.toggled.connect(self._toggle_plot)
        self.plot_scale.currentTextChanged.connect(
            lambda text: self.path_plot.set_y_scale(text.lower())
        )
        return self.plot_card

    def _build_statusbar(self) -> None:
        status = QStatusBar()
        status.setObjectName("appStatusBar")
        self.state_label = QLabel("●  Готово")
        self.state_label.setObjectName("readyStatus")
        self.cursor_label = QLabel("X = — мм   |   Y = — мм   |   |B| = — мТл")
        self.zoom_label = QLabel("Zoom = 100%")
        status.addWidget(self.state_label)
        status.addPermanentWidget(self.cursor_label, 1)
        status.addPermanentWidget(self.zoom_label)
        self.setStatusBar(status)

    def _connect_controls(self) -> None:
        panel = self.control_panel
        panel.layerChanged.connect(self.controller.set_layer_visibility)
        panel.addMagnetRequested.connect(self.controller.add_magnet)
        panel.magnetPositionEdited.connect(
            lambda magnet_id, x, y: self._safe_call(
                self.controller.set_magnet_position, magnet_id, x, y, interaction="full"
            )
        )
        panel.magnetAngleEdited.connect(
            lambda magnet_id, angle: self._safe_call(
                self.controller.set_magnet_angle, magnet_id, angle, interaction="full"
            )
        )
        panel.magnetDefinitionEdited.connect(self.controller.set_magnet_definition)
        panel.magnetEnabledEdited.connect(self.controller.set_magnet_enabled)
        panel.removeMagnetRequested.connect(self.controller.remove_magnet)
        panel.sensorPositionEdited.connect(
            lambda x, y: self._safe_call(self.controller.set_sensor_position, x, y, interaction="full")
        )
        panel.sensorAngleEdited.connect(self.controller.set_sensor_angle)
        panel.sensorModeEdited.connect(self.controller.set_sensor_mode)
        panel.alignSensorRequested.connect(self.controller.align_sensor_to_field)
        panel.presetRequested.connect(self.controller.apply_preset)

        self.analysis_page.pathEnabledChanged.connect(self.controller.set_path_enabled)
        self.analysis_page.pathPointEdited.connect(
            lambda point, x, y: self._safe_call(self.controller.set_path_point, point, x, y)
        )
        self.analysis_page.pathSamplesEdited.connect(
            lambda samples: self._safe_call(self.controller.set_path_samples, samples)
        )

        self.settings_page.normalizationChanged.connect(self.controller.set_normalization)
        self.settings_page.colorRangeModeChanged.connect(self.controller.set_color_range_mode)
        self.settings_page.percentileChanged.connect(
            lambda value: self._safe_call(self.controller.set_percentile_clip, value)
        )
        self.settings_page.gammaChanged.connect(
            lambda value: self._safe_call(self.controller.set_power_gamma, value)
        )
        self.settings_page.manualRangeChanged.connect(
            lambda minimum, maximum: self._safe_call(
                self.controller.set_manual_color_range, minimum, maximum
            )
        )
        self.settings_page.saveLastSceneChanged.connect(self.controller.set_save_last_scene)

        self.quick_heatmap.toggled.connect(
            lambda checked: self.controller.set_layer_visibility("heatmap", checked)
        )
        self.quick_lines.toggled.connect(
            lambda checked: self.controller.set_layer_visibility("field_lines", checked)
        )
        self.quick_grid.toggled.connect(
            lambda checked: self.controller.set_layer_visibility("grid", checked)
        )
        self.reset_view.clicked.connect(self.canvas.reset_view)

        if hasattr(self.canvas, "magnetDragged"):
            self.canvas.magnetDragged.connect(
                lambda magnet_id, x, y: self.controller.set_magnet_position(
                    magnet_id, x, y, interaction="drag"
                )
            )
            self.canvas.magnetDragFinished.connect(
                lambda magnet_id, x, y: self.controller.set_magnet_position(
                    magnet_id, x, y, interaction="full"
                )
            )
            self.canvas.magnetRotated.connect(
                lambda magnet_id, angle: self.controller.set_magnet_angle(
                    magnet_id, angle, interaction="drag"
                )
            )
            self.canvas.magnetRotationFinished.connect(
                lambda magnet_id, angle: self.controller.set_magnet_angle(
                    magnet_id, angle, interaction="full"
                )
            )
            self.canvas.sensorDragged.connect(
                lambda x, y: self.controller.set_sensor_position(x, y, interaction="drag")
            )
            self.canvas.sensorDragFinished.connect(
                lambda x, y: self.controller.set_sensor_position(x, y, interaction="full")
            )
            self.canvas.sensorRotated.connect(self.controller.set_sensor_angle)
            self.canvas.pathPointMoved.connect(self.controller.set_path_point)
            self.canvas.cursorWorldPositionChanged.connect(self._update_cursor)
            self.canvas.viewTransformChanged.connect(self._update_zoom)

    def _connect_controller(self) -> None:
        self.controller.sceneChanged.connect(self._render_scene)
        self.controller.fieldGridChanged.connect(self.canvas.set_field_grid)
        self.controller.sensorReadingChanged.connect(self._render_sensor_reading)
        self.controller.pathProfileChanged.connect(self._render_path_profile)
        self.controller.themeChanged.connect(self._apply_theme)
        self.controller.settingsChanged.connect(self._render_app_settings)
        self.controller.statusMessageChanged.connect(self.statusBar().showMessage)

    def _install_shortcuts(self) -> None:
        reset = QAction(self)
        reset.setShortcut(QKeySequence("R"))
        reset.triggered.connect(self.canvas.reset_view)
        self.addAction(reset)

    def _safe_call(self, function, *args, **kwargs) -> None:
        try:
            function(*args, **kwargs)
        except ValueError as exc:
            self.statusBar().showMessage(str(exc), 5000)

    def _render_scene(self, scene) -> None:
        self.control_panel.refresh(scene)
        self.canvas.set_scene(scene)
        self.analysis_page.refresh(scene)
        self.settings_page.refresh(scene, self.controller.app_settings())
        for widget, value in (
            (self.quick_heatmap, scene.view.show_heatmap),
            (self.quick_lines, scene.view.show_field_lines),
            (self.quick_grid, scene.view.show_grid),
        ):
            blocked = widget.blockSignals(True)
            widget.setChecked(value)
            widget.blockSignals(blocked)

    def _render_sensor_reading(self, reading) -> None:
        self.canvas.set_sensor_reading(reading)
        if reading is None:
            self.control_panel.sensor_reading.setText("— мТл")
        else:
            self.control_panel.sensor_reading.setText(f"{reading.value_mT:.3f} мТл")

    def _render_path_profile(self, profile) -> None:
        if profile is None:
            self.path_plot.clear_with_message("Задайте путь A-B на карте")
            self.analysis_page.path_plot.clear_with_message(
                "Включите путь A-B для построения графика"
            )
            return
        self.path_plot.set_profile(profile)
        self.analysis_page.set_profile(profile)

    def _render_app_settings(self, app_settings) -> None:
        self.settings_page.refresh(self.controller.scene(), app_settings)

    def _apply_theme(self, theme: str) -> None:
        should_animate = self._current_theme is not None and self.isVisible()
        self._cleanup_theme_overlay()
        qss_path = Path(__file__).parents[1] / "resources" / "qss" / f"{theme}.qss"
        resource_dir = qss_path.parents[1].as_posix()
        stylesheet = qss_path.read_text(encoding="utf-8").replace(
            "@RESOURCE_DIR@", resource_dir
        )
        QApplication.instance().setStyleSheet(stylesheet)
        self.theme_switch.set_theme(theme, animated=should_animate)
        self.canvas.set_theme(theme)
        self.path_plot.set_theme(theme)
        self.analysis_page.set_theme(theme)
        self._current_theme = theme

    def _cleanup_theme_overlay(self) -> None:
        if self._theme_fade is not None:
            self._theme_fade.stop()
            self._theme_fade.deleteLater()
            self._theme_fade = None
        if self._theme_overlay is not None:
            self._theme_overlay.deleteLater()
            self._theme_overlay = None

    def _show_help(self) -> None:
        if self._help_dialog is None:
            self._help_dialog = HelpDialog(self)
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def _switch_page(self, index: int) -> None:
        self._cleanup_theme_overlay()
        self.page_stack.setCurrentIndex(index)
        for page_index, button in self.nav_buttons.items():
            button.setChecked(page_index == index)

    def _toggle_plot(self, collapsed: bool) -> None:
        self.path_plot.setVisible(not collapsed)
        self.collapse_plot.setText("Развернуть" if collapsed else "Свернуть")

    def _update_cursor(self, x_mm: float, y_mm: float) -> None:
        self.cursor_label.setText(f"X = {x_mm:.1f} мм   |   Y = {y_mm:.1f} мм   |   |B| = — мТл")

    def _update_zoom(self, zoom: float) -> None:
        self.zoom_label.setText(f"Zoom = {zoom * 100:.0f}%")

    def closeEvent(self, event) -> None:
        if self._settings_service is not None:
            self._settings_service.save(
                self.controller.app_settings(),
                self.controller.scene(),
                self.saveGeometry(),
            )
        super().closeEvent(event)
