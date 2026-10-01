from __future__ import annotations

import json
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
from hallsim.core.enums import ColorRangeMode, FieldNormalization, SensorOrientationMode


class SettingsService:
    def __init__(
        self,
        settings: QSettings | None = None,
        scene_path: Path | None = None,
    ) -> None:
        self._settings = settings or QSettings("HallSim", "HallSim")
        if scene_path is None:
            data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
            scene_path = data_dir / "last_scene.json"
        self._scene_path = scene_path

    def load(self) -> AppSettings:
        theme = str(self._settings.value("appearance/theme", "light"))
        if theme not in {"light", "dark"}:
            theme = "light"
        save_last_scene = self._settings.value("scene/save_last", True, type=bool)
        last_zoom = self._settings.value("view/zoom", 1.0, type=float)
        scene = self._load_scene() if save_last_scene else None
        return AppSettings(
            theme=theme,
            last_zoom=last_zoom,
            save_last_scene=save_last_scene,
            last_scene=scene,
        )

    def save(self, app_settings: AppSettings, scene: SceneState, geometry: QByteArray) -> None:
        self._settings.setValue("appearance/theme", app_settings.theme)
        self._settings.setValue("window/geometry", geometry)
        self._settings.setValue("view/zoom", app_settings.last_zoom)
        self._settings.setValue("scene/save_last", app_settings.save_last_scene)
        self._settings.sync()
        if app_settings.save_last_scene:
            self._save_scene(scene)

    def restore_window_geometry(self) -> QByteArray | None:
        value = self._settings.value("window/geometry")
        return value if isinstance(value, QByteArray) and not value.isEmpty() else None

    def _load_scene(self) -> SceneState | None:
        try:
            payload = json.loads(self._scene_path.read_text(encoding="utf-8"))
            return self._scene_from_dict(payload)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
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
                "show_heatmap": scene.view.show_heatmap,
                "show_field_lines": scene.view.show_field_lines,
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
        if payload.get("version") != 1:
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
            show_heatmap=bool(view_payload["show_heatmap"]),
            show_field_lines=bool(view_payload["show_field_lines"]),
            show_grid=bool(view_payload["show_grid"]),
            normalization=FieldNormalization[view_payload["normalization"]],
            color_range_mode=ColorRangeMode[view_payload["color_range_mode"]],
            color_min_mT=view_payload["color_min_mT"],
            color_max_mT=view_payload["color_max_mT"],
            percentile_clip=float(view_payload["percentile_clip"]),
            power_gamma=float(view_payload["power_gamma"]),
        )
        return SceneState(
            magnets=magnets,
            sensor=sensor,
            path=path,
            view=view,
            revision=int(payload.get("revision", 0)),
        )

