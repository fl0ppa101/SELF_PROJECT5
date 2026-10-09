from __future__ import annotations

from copy import deepcopy
import math

from PyQt6.QtCore import QObject, pyqtSignal

from hallsim.app.config import MAX_GUI_MAGNETS, X_MAX_MM, X_MIN_MM, Y_MAX_MM, Y_MIN_MM
from hallsim.app.config import MAX_PATH_SAMPLES, MIN_PATH_SAMPLES
from hallsim.core.contracts import AppSettings, SceneState
from hallsim.core.enums import (
    ColorRangeMode,
    FieldNormalization,
    SensorOrientationMode,
    VisualizationPreset,
)
from hallsim.core.magnet_catalog import MAGNET_CATALOG

from .presets import PRESET_FACTORIES, single_magnet


class AppController(QObject):
    sceneChanged = pyqtSignal(object)
    fieldGridChanged = pyqtSignal(object)
    sensorReadingChanged = pyqtSignal(object)
    pathProfileChanged = pyqtSignal(object)
    themeChanged = pyqtSignal(str)
    settingsChanged = pyqtSignal(object)
    statusMessageChanged = pyqtSignal(str)
    recalculationRequested = pyqtSignal(object, str)
    catalogChanged = pyqtSignal(object)

    def __init__(
        self,
        scene: SceneState | None = None,
        app_settings: AppSettings | None = None,
        calculation_service=None,
        parent: QObject | None = None,
        *,
        catalog_service=None,
    ) -> None:
        super().__init__(parent)
        self._scene = deepcopy(scene) if scene is not None else single_magnet()
        self._catalog_service = catalog_service
        self._catalog = (
            dict(MAGNET_CATALOG)
            if catalog_service is None
            else catalog_service.definitions()
        )
        aliases = {
            "ferrite": "ferrite_y35",
            "ndfeb_medium": "ndfeb_n42",
            "ndfeb_strong": "ndfeb_n52",
        }
        for magnet in self._scene.magnets:
            magnet.definition_id = aliases.get(
                magnet.definition_id, magnet.definition_id
            )
            if magnet.definition_id not in self._catalog:
                magnet.definition_id = "ndfeb_n42"
        self._app_settings = (
            deepcopy(app_settings) if app_settings is not None else AppSettings()
        )
        self._theme = self._app_settings.theme
        self._calculation_service = calculation_service
        if calculation_service is not None:
            calculation_service.fieldGridReady.connect(self._accept_field_grid)
            calculation_service.sensorReadingReady.connect(self._accept_sensor_reading)
            calculation_service.pathProfileReady.connect(self._accept_path_profile)
            calculation_service.calculationFailed.connect(
                self._accept_calculation_error
            )

    def scene(self) -> SceneState:
        return deepcopy(self._scene)

    def app_settings(self) -> AppSettings:
        return deepcopy(self._app_settings)

    def magnet_definitions(self):
        return dict(self._catalog)

    def create_custom_magnet(self, name, moment_Am2):
        if self._catalog_service is None:
            raise ValueError("Каталог пользовательских магнитов не подключён")
        identifier = self._catalog_service.create_custom(name, moment_Am2)
        self._catalog = self._catalog_service.definitions()
        if hasattr(self._calculation_service, "update_catalog"):
            self._calculation_service.update_catalog(self._catalog)
        self.catalogChanged.emit(self.magnet_definitions())
        return identifier

    @property
    def theme(self) -> str:
        return self._theme

    def publish_initial_state(self) -> None:
        self.catalogChanged.emit(self.magnet_definitions())
        self._align_auto_sensor()
        self.sceneChanged.emit(self.scene())
        self.themeChanged.emit(self._theme)
        self.settingsChanged.emit(self.app_settings())
        self._request_calculation(self.scene(), "full", "all")

    def _magnet(self, magnet_id: int):
        for magnet in self._scene.magnets:
            if magnet.id == magnet_id:
                return magnet
        raise ValueError(f"Магнит {magnet_id} не найден")

    @staticmethod
    def _position(x_mm: float, y_mm: float) -> tuple[float, float]:
        if not X_MIN_MM <= x_mm <= X_MAX_MM:
            raise ValueError(f"X должен быть от {X_MIN_MM:g} до {X_MAX_MM:g} мм")
        if not Y_MIN_MM <= y_mm <= Y_MAX_MM:
            raise ValueError(f"Y должен быть от {Y_MIN_MM:g} до {Y_MAX_MM:g} мм")
        return float(x_mm), float(y_mm)

    @staticmethod
    def _angle(angle_deg: float) -> float:
        if not math.isfinite(angle_deg):
            raise ValueError("Угол должен быть конечным числом")
        return float(angle_deg) % 360.0

    def _physical_change(self, quality: str = "full", scope: str = "all") -> None:
        if scope in {"all", "sensor"}:
            self._align_auto_sensor()
        self._scene.revision += 1
        snapshot = self.scene()
        self.sceneChanged.emit(snapshot)
        self.recalculationRequested.emit(snapshot, quality)
        self._request_calculation(snapshot, quality, scope)

    def _request_calculation(self, scene: SceneState, quality: str, scope: str) -> None:
        service = self._calculation_service
        if service is None:
            return
        if hasattr(service, "update_scene"):
            service.update_scene(scene)
        if scope == "all":
            service.request_field_grid(scene, quality)
            service.request_sensor_reading(scene)
            if scene.path.enabled:
                service.request_path_profile(scene)
        elif scope == "sensor":
            service.request_sensor_reading(scene)
        elif scope == "path" and scene.path.enabled:
            service.request_path_profile(scene)

    def _accept_field_grid(self, grid) -> None:
        if grid.scene_revision == self._scene.revision:
            self.fieldGridChanged.emit(grid)

    def _accept_sensor_reading(self, reading) -> None:
        self.sensorReadingChanged.emit(reading)

    def _accept_path_profile(self, profile) -> None:
        if profile is None or profile.scene_revision == self._scene.revision:
            self.pathProfileChanged.emit(profile)

    def _align_auto_sensor(self):
        service = self._calculation_service
        if (
            self._scene.sensor.orientation_mode is SensorOrientationMode.AUTO
            and hasattr(service, "optimal_sensor_angle")
        ):
            angle = service.optimal_sensor_angle(self._scene)
            if angle is not None:
                self._scene.sensor.angle_deg = angle
            else:
                self.statusMessageChanged.emit("Направление поля не определено")

    def field_at_cursor(self, x_mm, y_mm):
        service = self._calculation_service
        if hasattr(service, "field_at"):
            return service.field_at(self._scene, x_mm, y_mm)
        return None

    def shutdown(self):
        if hasattr(self._calculation_service, "shutdown"):
            self._calculation_service.shutdown()

    def _accept_calculation_error(self, message: str, revision: int) -> None:
        if revision == self._scene.revision:
            self.statusMessageChanged.emit(message)

    def set_magnet_position(
        self,
        magnet_id: int,
        x_mm: float,
        y_mm: float,
        *,
        interaction: str = "full",
    ) -> None:
        magnet = self._magnet(magnet_id)
        x_mm, y_mm = self._position(x_mm, y_mm)
        if (magnet.x_mm, magnet.y_mm) == (x_mm, y_mm):
            if interaction != "drag":
                snapshot = self.scene()
                self.recalculationRequested.emit(snapshot, "full")
                self._request_calculation(snapshot, "full", "all")
            return
        magnet.x_mm, magnet.y_mm = x_mm, y_mm
        self._physical_change("drag" if interaction == "drag" else "full")

    def set_magnet_angle(
        self,
        magnet_id: int,
        angle_deg: float,
        *,
        interaction: str = "full",
    ) -> None:
        magnet = self._magnet(magnet_id)
        angle_deg = self._angle(angle_deg)
        if magnet.angle_deg == angle_deg:
            if interaction != "drag":
                snapshot = self.scene()
                self.recalculationRequested.emit(snapshot, "full")
                self._request_calculation(snapshot, "full", "all")
            return
        magnet.angle_deg = angle_deg
        self._physical_change("drag" if interaction == "drag" else "full")

    def set_magnet_definition(self, magnet_id: int, definition_id: str) -> None:
        if definition_id not in self._catalog:
            raise ValueError("Неизвестный тип магнита")
        magnet = self._magnet(magnet_id)
        if magnet.definition_id == definition_id:
            return
        magnet.definition_id = definition_id
        self._physical_change()

    def set_magnet_enabled(self, magnet_id: int, enabled: bool) -> None:
        magnet = self._magnet(magnet_id)
        if magnet.enabled == enabled:
            return
        magnet.enabled = enabled
        self._physical_change()

    def add_magnet(self) -> None:
        if len(self._scene.magnets) >= MAX_GUI_MAGNETS:
            self.statusMessageChanged.emit("В GUI допускается не более двух магнитов")
            return
        next_id = max((magnet.id for magnet in self._scene.magnets), default=0) + 1
        from hallsim.core.contracts import MagnetState

        self._scene.magnets.append(
            MagnetState(next_id, True, 30.0, 0.0, 180.0, "ndfeb_n42")
        )
        self._physical_change()

    def remove_magnet(self, magnet_id: int) -> None:
        if len(self._scene.magnets) <= 1:
            self.statusMessageChanged.emit(
                "В сцене должен остаться хотя бы один магнит"
            )
            return
        self._scene.magnets = [
            magnet for magnet in self._scene.magnets if magnet.id != magnet_id
        ]
        self._physical_change()

    def set_sensor_position(
        self,
        x_mm: float,
        y_mm: float,
        *,
        interaction: str = "full",
    ) -> None:
        x_mm, y_mm = self._position(x_mm, y_mm)
        sensor = self._scene.sensor
        if (sensor.x_mm, sensor.y_mm) == (x_mm, y_mm):
            if interaction != "drag":
                snapshot = self.scene()
                self.recalculationRequested.emit(snapshot, "full")
                self._request_calculation(snapshot, "full", "sensor")
            return
        sensor.x_mm, sensor.y_mm = x_mm, y_mm
        self._physical_change("drag" if interaction == "drag" else "full", "sensor")

    def set_sensor_angle(self, angle_deg: float, *, manual: bool = True) -> None:
        sensor = self._scene.sensor
        angle_deg = self._angle(angle_deg)
        mode = SensorOrientationMode.MANUAL if manual else sensor.orientation_mode
        if sensor.angle_deg == angle_deg and sensor.orientation_mode is mode:
            return
        sensor.angle_deg = angle_deg
        sensor.orientation_mode = mode
        self._physical_change(scope="sensor")

    def set_sensor_mode(self, mode: SensorOrientationMode) -> None:
        if self._scene.sensor.orientation_mode is mode:
            return
        self._scene.sensor.orientation_mode = mode
        self._physical_change(scope="sensor")

    def align_sensor_to_field(self) -> None:
        self._scene.sensor.orientation_mode = SensorOrientationMode.AUTO
        self._physical_change(scope="sensor")

    def set_path_point(self, point: str, x_mm: float, y_mm: float) -> None:
        x_mm, y_mm = self._position(x_mm, y_mm)
        point = point.upper()
        if point == "A":
            self._scene.path.ax_mm, self._scene.path.ay_mm = x_mm, y_mm
        elif point == "B":
            self._scene.path.bx_mm, self._scene.path.by_mm = x_mm, y_mm
        else:
            raise ValueError("Точка пути должна быть A или B")
        self._scene.path.enabled = True
        self._physical_change(scope="path")

    def set_path_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._scene.path.enabled == enabled:
            return
        self._scene.path.enabled = enabled
        self._physical_change(scope="path")
        if not enabled:
            self.pathProfileChanged.emit(None)

    def set_path_samples(self, samples: int) -> None:
        samples = int(samples)
        if not MIN_PATH_SAMPLES <= samples <= MAX_PATH_SAMPLES:
            raise ValueError(
                f"Число точек пути должно быть от {MIN_PATH_SAMPLES} до {MAX_PATH_SAMPLES}"
            )
        if self._scene.path.samples == samples:
            return
        self._scene.path.samples = samples
        self._physical_change(scope="path")

    def _view_change(self, attribute: str, value) -> None:
        if getattr(self._scene.view, attribute) == value:
            return
        setattr(self._scene.view, attribute, value)
        if attribute in {
            "normalization",
            "color_range_mode",
            "percentile_clip",
            "power_gamma",
            "color_min_mT",
            "color_max_mT",
        }:
            self._scene.view.preset = VisualizationPreset.CUSTOM
        self.sceneChanged.emit(self.scene())

    def set_visualization_preset(self, preset):
        if not isinstance(preset, VisualizationPreset):
            raise ValueError("Неизвестный режим отображения")
        view = self._scene.view
        view.preset = preset
        if preset is VisualizationPreset.ILLUSTRATIVE:
            view.normalization = FieldNormalization.POWER
            view.color_range_mode = ColorRangeMode.AUTO_PERCENTILE
            view.percentile_clip, view.power_gamma = 99.0, 0.4
        elif preset is VisualizationPreset.LINEAR:
            view.normalization = FieldNormalization.LINEAR
            view.color_range_mode = ColorRangeMode.AUTO_FULL
        self.sceneChanged.emit(self.scene())

    def set_palette(self, palette):
        if palette not in {"hall", "viridis", "turbo"}:
            raise ValueError("Неизвестная палитра")
        self._view_change("palette", palette)

    def set_line_density(self, density):
        if not math.isfinite(density) or not 0.25 <= density <= 2:
            raise ValueError("Плотность линий: от 0.25 до 2")
        self._view_change("line_density", float(density))

    def set_layer_visibility(self, layer: str, visible: bool) -> None:
        names = {
            "heatmap": "show_heatmap",
            "field_lines": "show_field_lines",
            "grid": "show_grid",
        }
        try:
            attribute = names[layer]
        except KeyError as exc:
            raise ValueError(f"Неизвестный слой: {layer}") from exc
        self._view_change(attribute, bool(visible))

    def set_normalization(self, normalization: FieldNormalization) -> None:
        if not isinstance(normalization, FieldNormalization):
            raise ValueError("Неизвестный режим нормализации")
        if (
            normalization is FieldNormalization.LOG
            and self._scene.view.color_range_mode is ColorRangeMode.MANUAL
        ):
            if (
                self._scene.view.color_min_mT is None
                or self._scene.view.color_min_mT <= 0
            ):
                self._scene.view.color_min_mT = 0.001
            if (
                self._scene.view.color_max_mT is None
                or self._scene.view.color_max_mT <= self._scene.view.color_min_mT
            ):
                self._scene.view.color_max_mT = max(
                    50.0, self._scene.view.color_min_mT * 10
                )
        self._view_change("normalization", normalization)

    def set_color_range_mode(self, mode: ColorRangeMode) -> None:
        if not isinstance(mode, ColorRangeMode):
            raise ValueError("Неизвестный режим цветового диапазона")
        if mode is ColorRangeMode.MANUAL:
            view = self._scene.view
            if view.color_min_mT is None:
                view.color_min_mT = (
                    0.001 if view.normalization is FieldNormalization.LOG else 0.0
                )
            if view.normalization is FieldNormalization.LOG and view.color_min_mT <= 0:
                view.color_min_mT = 0.001
            if view.color_max_mT is None or view.color_max_mT <= view.color_min_mT:
                view.color_max_mT = max(50.0, view.color_min_mT * 10)
        self._view_change("color_range_mode", mode)

    def set_percentile_clip(self, value: float) -> None:
        value = float(value)
        if not 90.0 <= value <= 100.0:
            raise ValueError("Percentile должен быть от 90 до 100%")
        self._view_change("percentile_clip", value)

    def set_power_gamma(self, value: float) -> None:
        value = float(value)
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("Gamma должна быть положительной")
        self._view_change("power_gamma", value)

    def set_manual_color_range(self, minimum_mT: float, maximum_mT: float) -> None:
        minimum_mT = float(minimum_mT)
        maximum_mT = float(maximum_mT)
        if (
            not math.isfinite(minimum_mT)
            or not math.isfinite(maximum_mT)
            or minimum_mT < 0.0
            or maximum_mT <= minimum_mT
        ):
            raise ValueError("Максимум цветовой шкалы должен быть больше минимума")
        if self._scene.view.normalization is FieldNormalization.LOG and minimum_mT <= 0:
            raise ValueError("Для Log минимум цветовой шкалы должен быть больше нуля")
        changed = (
            self._scene.view.color_min_mT != minimum_mT
            or self._scene.view.color_max_mT != maximum_mT
        )
        if not changed:
            return
        self._scene.view.color_min_mT = minimum_mT
        self._scene.view.color_max_mT = maximum_mT
        self._scene.view.preset = VisualizationPreset.CUSTOM
        self.sceneChanged.emit(self.scene())

    def set_save_last_scene(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._app_settings.save_last_scene == enabled:
            return
        self._app_settings.save_last_scene = enabled
        self.settingsChanged.emit(self.app_settings())

    def set_zoom(self, factor: float) -> None:
        if math.isfinite(factor) and factor > 0:
            self._app_settings.last_zoom = factor

    def apply_preset(self, preset_id: str) -> None:
        try:
            new_scene = PRESET_FACTORIES[preset_id]()
        except KeyError as exc:
            raise ValueError(f"Неизвестный пресет: {preset_id}") from exc
        new_scene.view = deepcopy(self._scene.view)
        new_scene.revision = self._scene.revision + 1
        self._scene = new_scene
        self._align_auto_sensor()
        snapshot = self.scene()
        self.sceneChanged.emit(snapshot)
        self.pathProfileChanged.emit(None)
        self.recalculationRequested.emit(snapshot, "full")
        self._request_calculation(snapshot, "full", "all")

    def set_theme(self, theme: str) -> None:
        if theme not in {"light", "dark"}:
            raise ValueError("Тема должна быть light или dark")
        if theme == self._theme:
            return
        self._theme = theme
        self._app_settings.theme = theme
        self.themeChanged.emit(theme)
        self.settingsChanged.emit(self.app_settings())
