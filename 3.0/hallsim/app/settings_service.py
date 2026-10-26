from __future__ import annotations

import json
import math
from pathlib import Path

from PyQt6.QtCore import QByteArray, QSettings, QStandardPaths

from hallsim.core.contracts import (
    AppSettings,
    MagnetState,
    PathState,
    SceneState,
    SensorState,
    ViewSettings,
)
from hallsim.core.enums import (
    ColorRangeMode,
    FieldNormalization,
    SensorOrientationMode,
    AppSection,
    VisualizationPreset,
)


class SettingsService:
    def __init__(
        self,
        settings: QSettings | None = None,
        scene_path: Path | None = None,
    ) -> None:
        self._settings = settings or QSettings("HallSim", "HallSim")
        if scene_path is None:
            data_dir = Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.AppDataLocation
                )
            )
            scene_path = data_dir / "last_scene.json"
        self._scene_path = scene_path
        self.warnings = []

    def load(self) -> AppSettings:
        self.warnings.clear()
        theme = str(self._settings.value("appearance/theme", "light"))
        if theme not in {"light", "dark"}:
            theme = "light"
        save_last_scene = self._settings.value("scene/save_last", True, type=bool)
        try:
            last_zoom = self._settings.value("view/zoom", 1.0, type=float)
            if not math.isfinite(last_zoom) or not 0.01 <= last_zoom <= 1000:
                last_zoom = 1.0
        except (ValueError, TypeError):
            last_zoom = 1.0
        scene = self._load_scene() if save_last_scene else None
        preferences = self._settings.value("visualization/view")
        if preferences is not None:
            try:
                from .presets import single_magnet

                base = scene if scene is not None else single_magnet()
                payload = self._scene_to_dict(base)
                payload["view"] = json.loads(str(preferences))
                scene = self._scene_from_dict(payload)
            except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
                self.warnings.append(
                    "Параметры отображения повреждены. Использованы исходные настройки."
                )
        section = str(self._settings.value("view/section", "VISUALIZATION"))
        return AppSettings(
            theme=theme,
            last_zoom=last_zoom,
            save_last_scene=save_last_scene,
            last_scene=scene,
            last_section=AppSection.__members__.get(section, AppSection.VISUALIZATION),
        )

    def save(
        self, app_settings: AppSettings, scene: SceneState, geometry: QByteArray
    ) -> None:
        self._settings.setValue("appearance/theme", app_settings.theme)
        self._settings.setValue("window/geometry", geometry)
        self._settings.setValue("view/zoom", app_settings.last_zoom)
        self._settings.setValue("scene/save_last", app_settings.save_last_scene)
        self._settings.setValue("view/section", app_settings.last_section.name)
        self._settings.setValue(
            "visualization/view", json.dumps(self._scene_to_dict(scene)["view"])
        )
        self._settings.sync()
        if self._settings.status() != QSettings.Status.NoError:
            raise OSError("Не удалось записать настройки приложения")
        if app_settings.save_last_scene:
            self._save_scene(scene)

    def restore_window_geometry(self) -> QByteArray | None:
        value = self._settings.value("window/geometry")
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def _load_scene(self) -> SceneState | None:
        try:
            payload = json.loads(self._scene_path.read_text(encoding="utf-8"))
            return self._scene_from_dict(payload)
        except FileNotFoundError:
            return None
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            OverflowError,
        ):
            self.warnings.append(
                "Последнюю сцену не удалось загрузить. Открыта исходная сцена."
            )
            return None

    def _save_scene(self, scene: SceneState) -> None:
        self._scene_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._scene_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._scene_to_dict(scene), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self._scene_path)

    @staticmethod
    def _scene_to_dict(scene: SceneState) -> dict:
        return {
            "version": 1,
            "magnets": [
                {
                    "id": magnet.id,
                    "enabled": magnet.enabled,
                    "x_mm": magnet.x_mm,
                    "y_mm": magnet.y_mm,
                    "angle_deg": magnet.angle_deg,
                    "definition_id": magnet.definition_id,
                }
                for magnet in scene.magnets
            ],
            "sensor": {
                "x_mm": scene.sensor.x_mm,
                "y_mm": scene.sensor.y_mm,
                "angle_deg": scene.sensor.angle_deg,
                "orientation_mode": scene.sensor.orientation_mode.name,
            },
            "path": {
                "enabled": scene.path.enabled,
                "ax_mm": scene.path.ax_mm,
                "ay_mm": scene.path.ay_mm,
                "bx_mm": scene.path.bx_mm,
                "by_mm": scene.path.by_mm,
                "samples": scene.path.samples,
            },
            "view": {
                "preset": scene.view.preset.name,
                "palette": scene.view.palette,
                "line_density": scene.view.line_density,
                "show_heatmap": scene.view.show_heatmap,
                "show_field_lines": scene.view.show_field_lines,
                "show_field_arrows": scene.view.show_field_arrows,
                "show_grid": scene.view.show_grid,
                "normalization": scene.view.normalization.name,
                "color_range_mode": scene.view.color_range_mode.name,
                "color_min_mT": scene.view.color_min_mT,
                "color_max_mT": scene.view.color_max_mT,
                "percentile_clip": scene.view.percentile_clip,
                "power_gamma": scene.view.power_gamma,
            },
            "revision": scene.revision,
        }

    @staticmethod
    def _scene_from_dict(payload: dict) -> SceneState:
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("Unsupported scene version")
        magnets = [MagnetState(**item) for item in payload["magnets"]]
        sensor_payload = payload["sensor"]
        sensor = SensorState(
            x_mm=float(sensor_payload["x_mm"]),
            y_mm=float(sensor_payload["y_mm"]),
            angle_deg=float(sensor_payload["angle_deg"]),
            orientation_mode=SensorOrientationMode[sensor_payload["orientation_mode"]],
        )
        path = PathState(**payload["path"])
        view_payload = payload["view"]
        view = ViewSettings(
            preset=VisualizationPreset[view_payload.get("preset", "ILLUSTRATIVE")],
            palette=view_payload.get("palette", "hall"),
            line_density=float(view_payload.get("line_density", 1.0)),
            show_heatmap=bool(view_payload["show_heatmap"]),
            show_field_lines=bool(view_payload["show_field_lines"]),
            show_field_arrows=bool(view_payload.get("show_field_arrows", False)),
            show_grid=bool(view_payload["show_grid"]),
            normalization=FieldNormalization[view_payload["normalization"]],
            color_range_mode=ColorRangeMode[view_payload["color_range_mode"]],
            color_min_mT=view_payload["color_min_mT"],
            color_max_mT=view_payload["color_max_mT"],
            percentile_clip=float(view_payload["percentile_clip"]),
            power_gamma=float(view_payload["power_gamma"]),
        )
        scene = SceneState(
            magnets=magnets,
            sensor=sensor,
            path=path,
            view=view,
            revision=int(payload.get("revision", 0)),
        )

        SettingsService._validate_scene(scene)
        return scene

    @staticmethod
    def _validate_scene(scene):
        def finite(value, low, high):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError("Некорректное значение в сохранённой сцене")

        def position(x, y):
            finite(x, -80, 80)
            finite(y, -50, 50)

        if not 1 <= len(scene.magnets) <= 2:
            raise ValueError("Некорректное число магнитов")
        identifiers = set()
        for magnet in scene.magnets:
            if type(magnet.id) is not int or magnet.id < 1 or magnet.id in identifiers:
                raise ValueError("Некорректный идентификатор магнита")
            identifiers.add(magnet.id)
            if type(magnet.enabled) is not bool or not isinstance(
                magnet.definition_id, str
            ):
                raise ValueError("Некорректные параметры магнита")
            position(magnet.x_mm, magnet.y_mm)
            finite(magnet.angle_deg, -360000, 360000)
            magnet.angle_deg %= 360
        position(scene.sensor.x_mm, scene.sensor.y_mm)
        finite(scene.sensor.angle_deg, -360000, 360000)
        scene.sensor.angle_deg %= 360
        p = scene.path
        position(p.ax_mm, p.ay_mm)
        position(p.bx_mm, p.by_mm)
        if (
            type(p.enabled) is not bool
            or type(p.samples) is not int
            or not 2 <= p.samples <= 5000
        ):
            raise ValueError("Некорректные параметры пути")
        if p.enabled and math.hypot(p.bx_mm - p.ax_mm, p.by_mm - p.ay_mm) < 1e-6:
            raise ValueError("Точки A и B должны различаться")
        v = scene.view
        if v.palette not in {"hall", "viridis", "turbo"}:
            raise ValueError("Неизвестная палитра")
        finite(v.line_density, 0.25, 2)
        finite(v.percentile_clip, 90, 100)
        finite(v.power_gamma, 0.05, 3)
        if v.color_range_mode is ColorRangeMode.MANUAL:
            finite(v.color_min_mT, 0, 1_000_000)
            finite(v.color_max_mT, 0, 1_000_000)
            if (
                v.color_max_mT <= v.color_min_mT
                or v.normalization is FieldNormalization.LOG
                and v.color_min_mT <= 0
            ):
                raise ValueError("Некорректный цветовой диапазон")
