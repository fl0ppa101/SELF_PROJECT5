from hallsim.core.contracts import (
    MagnetState,
    PathState,
    SceneState,
    SensorState,
    ViewSettings,
)
from hallsim.core.enums import SensorOrientationMode


def _sensor() -> SensorState:
    return SensorState(
        x_mm=0.0,
        y_mm=30.0,
        angle_deg=0.0,
        orientation_mode=SensorOrientationMode.AUTO,
    )


def _disabled_path() -> PathState:
    return PathState(
        enabled=False,
        ax_mm=-60.0,
        ay_mm=0.0,
        bx_mm=60.0,
        by_mm=0.0,
    )


def single_magnet() -> SceneState:
    return SceneState(
        magnets=[MagnetState(1, True, 0.0, 0.0, 0.0, "ndfeb_n42")],
        sensor=_sensor(),
        path=_disabled_path(),
        view=ViewSettings(),
    )


def like_poles() -> SceneState:
    return SceneState(
        magnets=[
            MagnetState(1, True, -30.0, 0.0, 0.0, "ndfeb_n42"),
            MagnetState(2, True, 30.0, 0.0, 180.0, "ndfeb_n42"),
        ],
        sensor=_sensor(),
        path=_disabled_path(),
        view=ViewSettings(),
    )


def opposite_poles() -> SceneState:
    return SceneState(
        magnets=[
            MagnetState(1, True, -30.0, 0.0, 0.0, "ndfeb_n42"),
            MagnetState(2, True, 30.0, 0.0, 0.0, "ndfeb_n42"),
        ],
        sensor=_sensor(),
        path=_disabled_path(),
        view=ViewSettings(),
    )


PRESET_FACTORIES = {
    "single_magnet": single_magnet,
    "like_poles": like_poles,
    "opposite_poles": opposite_poles,
}
