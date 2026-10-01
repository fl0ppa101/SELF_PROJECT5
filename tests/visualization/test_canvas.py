from dataclasses import replace
import math
import numpy as np
import pytest
from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtTest import QSignalSpy, QTest
from hallsim.core.contracts import FieldPoint, SensorReading
from hallsim.core.enums import FieldStatus
from hallsim.visualization.field_canvas import FieldCanvas
from hallsim.visualization.mock_data import mock_scene
from hallsim.visualization.object_layer import rectangle_hit


@pytest.fixture
def canvas(qapp):
    widget = FieldCanvas()
    widget.resize(920, 650)
    widget.set_scene(mock_scene())
    widget.show()
    qapp.processEvents()
    widget.reset_view()
    yield widget
    widget.shutdown()
    widget.close()
    qapp.processEvents()


def test_transform_round_trip_before_and_after_zoom_pan(canvas, qapp):
    for phase in range(3):
        for x, y in [(-80., -50.), (0., 0.), (27.123, -17.875), (80., 50.)]:
            np.testing.assert_allclose(canvas.screen_to_world(canvas.world_to_screen(x, y)), [x, y], atol=1e-9)
        canvas.zoom_in()
        canvas.view_box.translateBy(x=7, y=-3)
        qapp.processEvents()


def test_zoom_does_not_change_colors_or_recreate_image(canvas, asymmetric_grid, qapp):
    canvas.set_field_grid(asymmetric_grid)
    item = canvas.heatmap.image
    scale, data = canvas.heatmap.scale, canvas.heatmap.image.image.copy()
    canvas.zoom_in()
    canvas.zoom_out()
    canvas.view_box.translateBy(x=22, y=-8)
    qapp.processEvents()
    assert canvas.heatmap.image is item
    assert canvas.heatmap.scale == scale
    np.testing.assert_array_equal(canvas.heatmap.image.image, data)


def test_rotated_magnet_hit_test_has_exact_20_by_8_body():
    assert rectangle_hit(9.9, 3.9, 0, 0, 0, 20, 8)
    assert not rectangle_hit(10.1, 0, 0, 0, 0, 20, 8)
    assert rectangle_hit(0, 9.9, 0, 0, 90, 20, 8)
    assert not rectangle_hit(5, 0, 0, 0, 90, 20, 8)
    assert rectangle_hit(5, 5, 0, 0, 45, 20, 8)


def test_magnet_s_to_n_rotation_and_sensor_plate(canvas):
    scene = mock_scene()
    scene.magnets[0].angle_deg = 90
    scene.sensor.angle_deg = 35
    canvas.set_scene(scene)
    magnet = canvas.objects.magnets[1]
    south = magnet.mapToParent(QPointF(-5, 0))
    north = magnet.mapToParent(QPointF(5, 0))
    assert north.y() > south.y()
    assert north.x() == pytest.approx(south.x(), abs=1e-12)
    assert canvas.objects.sensor.rotation() == pytest.approx(-55)
    plate = np.array([math.cos(math.radians(-55)), math.sin(math.radians(-55))])
    sensitive = np.array([math.cos(math.radians(35)), math.sin(math.radians(35))])
    assert np.dot(plate, sensitive) == pytest.approx(0, abs=1e-12)


def test_sensor_and_path_hit_test(canvas):
    scene = mock_scene()
    scene.sensor.angle_deg = 0
    scene.path.enabled = True
    canvas.set_scene(scene)
    assert canvas.hit_test(0., 30.) == ("sensor", -1)
    assert canvas.hit_test(0., 34.) == ("sensor", -1)
    assert canvas.hit_test(-70., 0.) == ("path", "A")
    assert canvas.hit_test(70., 0.) == ("path", "B")
    assert canvas.hit_test(0., 0.) == ("magnet", 1)
    assert canvas.hit_test(55., 42.) is None


def _viewport_pos(canvas, x, y):
    return (canvas.world_to_screen(x, y)-canvas._viewport_origin()).toPoint()


def test_drag_emits_millimeters_with_body_grab_offset(canvas):
    started = QSignalSpy(canvas.magnetDragStarted)
    moved = QSignalSpy(canvas.magnetDragged)
    finished = QSignalSpy(canvas.magnetDragFinished)
    viewport = canvas.graphics.viewport()
    # Grab right of center; magnet center should remain offset from the cursor.
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, 3, 1))
    QTest.mouseMove(viewport, _viewport_pos(canvas, 23, 11))
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, 23, 11))
    assert len(started) == 1 and started[0][0] == 1
    assert len(moved) >= 1 and len(finished) == 1
    assert finished[0][0] == 1
    np.testing.assert_allclose(finished[0][1:], [20., 10.], atol=.4)
    assert canvas.streamlines.mode == "full"


def test_path_creation_two_clicks_and_drag_signal(canvas):
    signals = QSignalSpy(canvas.pathPointMoved)
    completed = QSignalSpy(canvas.pathCreationFinished)
    canvas.set_path_creation_enabled(True)
    for x, y in [(-30., -20.), (40., 20.)]:
        QTest.mouseClick(canvas.graphics.viewport(), Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, x, y))
    assert len(signals) == 2
    assert signals[0][0] == "A" and signals[1][0] == "B"
    np.testing.assert_allclose(signals[0][1:], [-30, -20], atol=.3)
    np.testing.assert_allclose(signals[1][1:], [40, 20], atol=.3)
    assert len(completed) == 1


def test_visualization_preserves_scene_input(canvas):
    scene = mock_scene()
    canvas.set_scene(scene)
    canvas.objects.set_selection(("magnet", 1))
    QTest.mouseClick(canvas.graphics.viewport(), Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, 2, 0))
    assert scene.magnets[0].x_mm == 0
    assert scene.revision == 0


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_and_missing_data(canvas, asymmetric_grid, theme, qapp):
    canvas.set_theme(theme)
    canvas.set_field_grid(None)
    assert canvas.empty_label.isVisible()
    assert not canvas.heatmap.image.isVisible()
    canvas.set_sensor_reading(None)
    nan_reading = SensorReading(np.nan, FieldPoint(np.nan, np.nan, np.nan, None, FieldStatus.INSIDE_SINGULARITY))
    canvas.set_sensor_reading(nan_reading)
    grid = replace(asymmetric_grid, modB_mT=np.full_like(asymmetric_grid.modB_mT, np.nan))
    canvas.set_field_grid(grid)
    qapp.processEvents()
    assert np.isnan(canvas.heatmap.image.image).all()
    assert canvas.colorbar.theme == canvas.objects.sensor.theme


def test_middle_button_pan_changes_transform(canvas, qapp):
    viewport = canvas.graphics.viewport()
    before = canvas.world_to_screen(0, 0)
    p = _viewport_pos(canvas, 0, 0)
    QTest.mousePress(viewport, Qt.MouseButton.MiddleButton, pos=p)
    QTest.mouseMove(viewport, p+QPoint(35, 20))
    QTest.mouseRelease(viewport, Qt.MouseButton.MiddleButton, pos=p+QPoint(35, 20))
    qapp.processEvents()
    after = canvas.world_to_screen(0, 0)
    assert after.x()-before.x() == pytest.approx(35, abs=1)
    assert after.y()-before.y() == pytest.approx(20, abs=1)


def test_rotation_handles_emit_normalized_angles(canvas):
    magnet_rotation = QSignalSpy(canvas.magnetRotated)
    magnet_finish = QSignalSpy(canvas.magnetRotationFinished)
    viewport = canvas.graphics.viewport()
    canvas.objects.set_selection(("magnet", 1))
    # Handle starts at +Y; dragging to -X gives a 90 degree S->N angle.
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, 0, 12))
    QTest.mouseMove(viewport, _viewport_pos(canvas, -12, 0))
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, -12, 0))
    assert len(magnet_rotation) >= 1 and len(magnet_finish) == 1
    assert magnet_finish[0][1] == pytest.approx(90, abs=2)
    sensor_rotation = QSignalSpy(canvas.sensorRotated)
    canvas.objects.set_selection(("sensor", -1))
    h = canvas.objects.sensor.handle_world()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, h.x(), h.y()))
    QTest.mouseMove(viewport, _viewport_pos(canvas, 0, 42))
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, 0, 42))
    assert len(sensor_rotation) >= 1
    assert sensor_rotation[-1][0] == pytest.approx(90, abs=2)


def test_sensor_drag_and_path_endpoint_drag(canvas):
    scene = mock_scene()
    scene.path.enabled = True
    canvas.set_scene(scene)
    sensor_started = QSignalSpy(canvas.sensorDragStarted)
    sensor_finished = QSignalSpy(canvas.sensorDragFinished)
    viewport = canvas.graphics.viewport()
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, 0, 30))
    QTest.mouseMove(viewport, _viewport_pos(canvas, 12, 22))
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, 12, 22))
    assert len(sensor_started) == 1 and len(sensor_finished) == 1
    np.testing.assert_allclose(sensor_finished[0], [12., 22.], atol=.4)
    moved = QSignalSpy(canvas.pathPointMoved)
    QTest.mousePress(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, -70, 0))
    QTest.mouseMove(viewport, _viewport_pos(canvas, -50, -20))
    QTest.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=_viewport_pos(canvas, -50, -20))
    assert moved[-1][0] == "A"
    np.testing.assert_allclose(moved[-1][1:], [-50., -20.], atol=.4)
