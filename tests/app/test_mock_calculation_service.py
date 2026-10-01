from hallsim.app.controller import AppController
from hallsim.app.mock_calculation_service import MockCalculationService
from hallsim.core.config import DRAG_GRID_SIZE, FULL_GRID_SIZE


def test_initial_full_grid_is_published(qtbot):
    service = MockCalculationService()
    controller = AppController(calculation_service=service)

    with qtbot.waitSignal(controller.fieldGridChanged, timeout=1000) as blocker:
        controller.publish_initial_state()

    grid = blocker.args[0]
    nx, ny = FULL_GRID_SIZE
    assert grid.modB_mT.shape == (ny, nx)
    assert grid.scene_revision == 0


def test_drag_uses_reduced_grid(qtbot):
    service = MockCalculationService()
    controller = AppController(calculation_service=service)

    with qtbot.waitSignal(controller.fieldGridChanged, timeout=1000) as blocker:
        controller.set_magnet_position(1, 5.0, 5.0, interaction="drag")

    grid = blocker.args[0]
    nx, ny = DRAG_GRID_SIZE
    assert grid.modB_mT.shape == (ny, nx)
    assert grid.scene_revision == controller.scene().revision


def test_sensor_change_does_not_request_field_grid(qtbot):
    service = MockCalculationService()
    controller = AppController(calculation_service=service)
    grid_emissions = []
    controller.fieldGridChanged.connect(grid_emissions.append)

    with qtbot.waitSignal(controller.sensorReadingChanged, timeout=1000):
        controller.set_sensor_position(10.0, 15.0)

    assert grid_emissions == []

