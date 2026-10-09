import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings

from .controller import AppController
from .lab_window import MainWindow
from .lab_controller import ExperimentController, SensorStudyController
from .magnet_catalog_service import MagnetCatalogService
from .mock_calculation_service import MockCalculationService
from .settings_service import SettingsService


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("HallSim Lab")
    app.setOrganizationName("HallSim")
    settings_service = SettingsService(settings=QSettings("HallSim", "HallSimLab"))
    app_settings = settings_service.load()
    catalog_service = MagnetCatalogService()
    if "--mock" in sys.argv:
        calculation_service = MockCalculationService()
    else:
        from .calculation_service import CalculationService

        calculation_service = CalculationService(catalog_service.definitions())
    controller = AppController(
        scene=app_settings.last_scene,
        app_settings=app_settings,
        calculation_service=calculation_service,
        catalog_service=catalog_service,
    )
    if "--mock" in sys.argv:
        from .mock_lab_engine import MockLabEngine

        engine = MockLabEngine()
    else:
        from hallsim.physics.engine import PhysicsEngine

        engine = PhysicsEngine(catalog_service.definitions())
    experiment = ExperimentController(engine, catalog_service)
    study = SensorStudyController(engine, catalog_service)
    window = MainWindow(controller, experiment, study, settings_service)
    window.show()
    app.aboutToQuit.connect(window.shutdown)
    return app.exec()
