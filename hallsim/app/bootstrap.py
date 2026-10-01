import sys

from PyQt6.QtWidgets import QApplication

from .controller import AppController
from .main_window import MainWindow
from .mock_calculation_service import MockCalculationService
from .settings_service import SettingsService


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("HallSim")
    app.setOrganizationName("HallSim")
    settings_service = SettingsService()
    app_settings = settings_service.load()
    calculation_service = MockCalculationService()
    controller = AppController(
        scene=app_settings.last_scene,
        app_settings=app_settings,
        calculation_service=calculation_service,
    )
    window = MainWindow(controller, settings_service=settings_service)
    window.show()
    return app.exec()
