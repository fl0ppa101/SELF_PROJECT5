import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QSettings, QStandardPaths, QTimer

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
    # Keep the existing data directory when changing the public application name.
    data_dir = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    )
    app.setApplicationName("Датчики Холла")
    app.setApplicationDisplayName("Датчики Холла")
    settings_service = SettingsService(
        settings=QSettings("HallSim", "HallSimLab"),
        scene_path=data_dir / "last_scene.json",
    )
    app_settings = settings_service.load()
    catalog_service = MagnetCatalogService(path=data_dir / "custom_magnets.json")
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
    if settings_service.warnings:
        QTimer.singleShot(
            0,
            lambda: QMessageBox.warning(
                window, "Восстановление настроек", "\n".join(settings_service.warnings)
            ),
        )
    app.aboutToQuit.connect(window.shutdown)
    return app.exec()
