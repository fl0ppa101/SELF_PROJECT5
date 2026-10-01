import sys

from PyQt6.QtWidgets import QApplication

from .controller import AppController
from .calculation_service import CalculationService
from .main_window import MainWindow
from .magnet_catalog_service import MagnetCatalogService
from .mock_calculation_service import MockCalculationService
from .settings_service import SettingsService


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("HallSim")
    app.setOrganizationName("HallSim")
    settings_service = SettingsService()
    app_settings = settings_service.load()
    catalog_service = MagnetCatalogService()
    calculation_service = MockCalculationService() if "--mock" in sys.argv else CalculationService(catalog_service.definitions())
    controller = AppController(
        scene=app_settings.last_scene,
        app_settings=app_settings,
        calculation_service=calculation_service,
        catalog_service=catalog_service,
    )
    window = MainWindow(controller, settings_service=settings_service)
    window.show()
    app.aboutToQuit.connect(calculation_service.shutdown if hasattr(calculation_service, "shutdown") else lambda: None)
    app.aboutToQuit.connect(window.canvas.shutdown)
    return app.exec()
