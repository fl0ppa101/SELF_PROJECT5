import pytest

from hallsim.app.controller import AppController
from hallsim.core.enums import ColorRangeMode, FieldNormalization, SensorOrientationMode


def test_initial_scene_matches_single_magnet_preset(qtbot):
    controller = AppController()

    scene = controller.scene()

    assert scene.revision == 0
    assert len(scene.magnets) == 1
    assert (scene.magnets[0].x_mm, scene.magnets[0].y_mm) == (0.0, 0.0)
    assert scene.sensor.orientation_mode is SensorOrientationMode.AUTO
    assert scene.path.enabled is False


def test_physical_change_increments_revision_and_requests_calculation(qtbot):
    controller = AppController()
    with qtbot.waitSignal(controller.recalculationRequested, timeout=1000) as blocker:
        controller.set_magnet_position(1, 12.0, -4.0, interaction="drag")

    scene = controller.scene()
    assert scene.revision == 1
    assert (scene.magnets[0].x_mm, scene.magnets[0].y_mm) == (12.0, -4.0)
    assert blocker.args[1] == "drag"


def test_drag_finish_requests_full_quality_even_at_same_position(qtbot):
    controller = AppController()
    controller.set_magnet_position(1, 10.0, 5.0, interaction="drag")

    with qtbot.waitSignal(controller.recalculationRequested, timeout=1000) as blocker:
        controller.set_magnet_position(1, 10.0, 5.0, interaction="full")

    assert blocker.args[1] == "full"
    assert controller.scene().revision == 1


def test_view_change_does_not_increment_revision(qtbot):
    controller = AppController()

    controller.set_layer_visibility("grid", True)

    assert controller.scene().view.show_grid is True
    assert controller.scene().revision == 0


def test_visualization_settings_do_not_increment_revision(qtbot):
    controller = AppController()

    controller.set_normalization(FieldNormalization.LOG)
    controller.set_color_range_mode(ColorRangeMode.MANUAL)
    controller.set_manual_color_range(0.1, 25.0)

    scene = controller.scene()
    assert scene.view.normalization is FieldNormalization.LOG
    assert scene.view.color_range_mode is ColorRangeMode.MANUAL
    assert (scene.view.color_min_mT, scene.view.color_max_mT) == (0.1, 25.0)
    assert scene.revision == 0


def test_enabling_path_requests_profile_and_increments_revision(qtbot):
    controller = AppController()

    controller.set_path_enabled(True)

    assert controller.scene().path.enabled is True
    assert controller.scene().revision == 1


def test_gui_never_adds_more_than_two_magnets(qtbot):
    controller = AppController()

    controller.add_magnet()
    controller.add_magnet()

    assert len(controller.scene().magnets) == 2


def test_manual_sensor_rotation_switches_mode(qtbot):
    controller = AppController()

    controller.set_sensor_angle(125.0)

    assert controller.scene().sensor.angle_deg == 125.0
    assert controller.scene().sensor.orientation_mode is SensorOrientationMode.MANUAL


def test_presets_have_specified_pole_orientations(qtbot):
    controller = AppController()

    controller.apply_preset("like_poles")
    like = controller.scene()
    assert [magnet.angle_deg for magnet in like.magnets] == [0.0, 180.0]

    controller.apply_preset("opposite_poles")
    opposite = controller.scene()
    assert [magnet.angle_deg for magnet in opposite.magnets] == [0.0, 0.0]


@pytest.mark.parametrize(
    ("x_mm", "y_mm"),
    [(-80.1, 0.0), (80.1, 0.0), (0.0, -50.1), (0.0, 50.1)],
)
def test_position_validation_uses_specified_workspace(qtbot, x_mm, y_mm):
    controller = AppController()

    with pytest.raises(ValueError):
        controller.set_magnet_position(1, x_mm, y_mm)
