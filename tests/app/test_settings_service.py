from PyQt6.QtCore import QSettings

from hallsim.app.presets import like_poles
from hallsim.app.settings_service import SettingsService
from hallsim.core.contracts import AppSettings
from hallsim.core.enums import ColorRangeMode, FieldNormalization


def test_settings_and_scene_round_trip(tmp_path):
    native = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    service = SettingsService(native, tmp_path / "scene.json")
    scene = like_poles()
    scene.view.normalization = FieldNormalization.LOG
    scene.view.color_range_mode = ColorRangeMode.MANUAL
    scene.view.color_min_mT = 0.2
    scene.view.color_max_mT = 18.0
    settings = AppSettings(theme="dark", last_zoom=1.4, save_last_scene=True)

    service.save(settings, scene, b"")
    restored = service.load()

    assert restored.theme == "dark"
    assert restored.last_zoom == 1.4
    assert restored.last_scene is not None
    assert len(restored.last_scene.magnets) == 2
    assert restored.last_scene.view.normalization is FieldNormalization.LOG
    assert restored.last_scene.view.color_range_mode is ColorRangeMode.MANUAL
    assert restored.last_scene.view.color_max_mT == 18.0


def test_corrupt_scene_falls_back_without_crashing(tmp_path):
    native = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    scene_path = tmp_path / "scene.json"
    scene_path.write_text("not json", encoding="utf-8")
    native.setValue("scene/save_last", True)
    service = SettingsService(native, scene_path)

    restored = service.load()

    assert restored.last_scene is None

