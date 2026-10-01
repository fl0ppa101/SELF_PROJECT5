from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import QObject, pyqtSignal

from hallsim.core.config import MAX_GUI_MAGNETS, X_MAX_MM, X_MIN_MM, Y_MAX_MM, Y_MIN_MM
from hallsim.core.config import MAX_PATH_SAMPLES, MIN_PATH_SAMPLES
from hallsim.core.contracts import AppSettings, SceneState
from hallsim.core.enums import ColorRangeMode, FieldNormalization, SensorOrientationMode

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

    def __init__(
        self,
        scene: SceneState | None = None,
        app_settings: AppSettings | None = None,
        calculation_service=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._scene = deepcopy(scene) if scene is not None else single_magnet()
        self._app_settings = deepcopy(app_settings) if app_settings is not None else AppSettings()
        self._theme = self._app_settings.theme
        self._calculation_service = calculation_service
        if calculation_service is not None:
            calculation_service.fieldGridReady.connect(self._accept_field_grid)
            calculation_service.sensorReadingReady.connect(self._accept_sensor_reading)
            calculation_service.pathProfileReady.connect(self._accept_path_profile)
            calculation_service.calculationFailed.connect(self._accept_calculation_error)

    def scene(self) -> SceneState:
        return deepcopy(self._scene)

    def app_settings(self) -> AppSettings:
        return deepcopy(self._app_settings)

    @property
    def theme(self) -> str:
        return self._theme

    def publish_initial_state(self) -> None:
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
        return float(angle_deg) % 360.0

    def _physical_change(self, quality: str = "full", scope: str = "all") -> None:
        self._scene.revision += 1
        snapshot = self.scene()
        self.sceneChanged.emit(snapshot)
        self.recalculationRequested.emit(snapshot, quality)
        self._request_calculation(snapshot, quality, scope)

    def _request_calculation(self, scene: SceneState, quality: str, scope: str) -> None:
        service = self._calculation_service
        if service is None:
            return
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
        if profile.scene_revision == self._scene.revision:
            self.pathProfileChanged.emit(profile)

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
            MagnetState(next_id, True, 30.0, 0.0, 180.0, "ndfeb_medium")
        )
        self._physical_change()

    def remove_magnet(self, magnet_id: int) -> None:
        if len(self._scene.magnets) <= 1:
            self.statusMessageChanged.emit("В сцене должен остаться хотя бы один магнит")
            return
        self._scene.magnets = [magnet for magnet in self._scene.magnets if magnet.id != magnet_id]
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
        self.statusMessageChanged.emit("Запрошено выравнивание датчика по полю")

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
        self.sceneChanged.emit(self.scene())

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
        self._view_change("normalization", normalization)

    def set_color_range_mode(self, mode: ColorRangeMode) -> None:
        if not isinstance(mode, ColorRangeMode):
            raise ValueError("Неизвестный режим цветового диапазона")
        self._view_change("color_range_mode", mode)

    def set_percentile_clip(self, value: float) -> None:
        value = float(value)
        if not 90.0 <= value <= 100.0:
            raise ValueError("Percentile должен быть от 90 до 100%")
        self._view_change("percentile_clip", value)

    def set_power_gamma(self, value: float) -> None:
        value = float(value)
        if value <= 0.0:
            raise ValueError("Gamma должна быть положительной")
        self._view_change("power_gamma", value)

    def set_manual_color_range(self, minimum_mT: float, maximum_mT: float) -> None:
        minimum_mT = float(minimum_mT)
        maximum_mT = float(maximum_mT)
        if minimum_mT < 0.0 or maximum_mT <= minimum_mT:
            raise ValueError("Максимум цветовой шкалы должен быть больше минимума")
        changed = (
            self._scene.view.color_min_mT != minimum_mT
            or self._scene.view.color_max_mT != maximum_mT
        )
        if not changed:
            return
        self._scene.view.color_min_mT = minimum_mT
        self._scene.view.color_max_mT = maximum_mT
        self.sceneChanged.emit(self.scene())

    def set_save_last_scene(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._app_settings.save_last_scene == enabled:
            return
        self._app_settings.save_last_scene = enabled
        self.settingsChanged.emit(self.app_settings())

    def apply_preset(self, preset_id: str) -> None:
        try:
            new_scene = PRESET_FACTORIES[preset_id]()
        except KeyError as exc:
            raise ValueError(f"Неизвестный пресет: {preset_id}") from exc
        new_scene.revision = self._scene.revision + 1
        self._scene = new_scene
        snapshot = self.scene()
        self.sceneChanged.emit(snapshot)
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
