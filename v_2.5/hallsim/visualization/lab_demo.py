"""Three standalone visual fixtures; independent of Physics and App."""

import numpy as np
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QPushButton,
    QComboBox,
    QLabel,
)
from hallsim.core.contracts import (
    ExperimentPointResult,
    ExperimentComparison,
    PathProfile,
    SensorStudyCurve,
)
from hallsim.core.enums import AppSection, MeasurementSource, SensorStudyAxis
from .field_canvas import FieldCanvas
from .lab_plots import ExperimentPlot, SensorStudyPlot
from .mock_data import mock_scene
from .theme import stylesheet


class LaboratoryDemo(QWidget):
    def __init__(self, visualization, theme="light", mode="visualization"):
        super().__init__()
        self.setWindowTitle("HallSim · три визуальных режима · mock")
        self.resize(1380, 940)
        self.setStyleSheet(stylesheet(theme))
        self.visualization = visualization
        self.tabs = QTabWidget()
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        self.tabs.addTab(visualization, "Визуализация")
        experiment = QWidget()
        exp_layout = QVBoxLayout(experiment)
        exp_layout.addWidget(
            QLabel(
                "Тестовые точки: серые — ожидают, зелёные — готовы, крестик — недопустимая точка"
            )
        )
        scene = mock_scene("opposite_poles")
        scene.path.enabled = True
        scene.path.ay_mm = scene.path.by_mm = 15.0
        self.experiment_canvas = FieldCanvas()
        self.experiment_canvas.set_mode(AppSection.EXPERIMENT)
        self.experiment_canvas.set_scene(scene)
        self.experiment_canvas.set_theme(theme)
        self.experiment_canvas.set_interaction_locked(True)
        self.experiment_canvas.sensor_translation_enabled = False
        xs = np.linspace(-70, 70, 20)
        values = 2 + 4 * np.exp(-((xs / 30) ** 2))
        values[7] = np.nan
        points = [
            ExperimentPointResult(
                float(x + 70),
                float(x),
                15.0,
                MeasurementSource.AUTOMATIC,
                36,
                0.05,
                float(value),
            )
            for x, value in zip(xs[:15], values[:15])
        ]
        self.experiment_canvas.set_experiment_points(points)
        self.experiment_canvas.set_experiment_pending_points(
            [(float(x + 70), float(x), 15.0) for x in xs[15:]]
        )
        self.experiment_canvas.set_active_experiment_point(
            (float(xs[15] + 70), float(xs[15]), 15.0)
        )
        exp_layout.addWidget(self.experiment_canvas, 1)
        self.experiment_plot = ExperimentPlot()
        self.experiment_plot.set_measurements(points)
        self.experiment_plot.set_theme(theme)
        exp_layout.addWidget(self.experiment_plot)
        compare = QPushButton("Показать тестовую теорию")
        distances = np.linspace(0, 140, 500)
        profile = PathProfile(
            distances,
            2.1 + 4 * np.exp(-(((distances - 70) / 30) ** 2)),
            np.ones(500, dtype=bool),
            0,
        )
        theory = np.array([p.measured_modB_mT + 0.1 for p in points])
        comparison = ExperimentComparison(
            np.array([p.s_mm for p in points]),
            np.array([p.measured_modB_mT for p in points]),
            theory,
            np.full(len(points), 0.1),
            0.1,
            profile,
        )
        compare.clicked.connect(lambda: self.experiment_plot.set_comparison(comparison))
        exp_layout.addWidget(compare)
        self.tabs.addTab(experiment, "Эксперимент")
        study = QWidget()
        study_layout = QVBoxLayout(study)
        self.study_canvas = FieldCanvas()
        self.study_canvas.set_mode(AppSection.SENSOR_STUDY)
        self.study_canvas.set_scene(mock_scene())
        self.study_canvas.set_theme(theme)
        study_layout.addWidget(self.study_canvas, 1)
        selector = QComboBox()
        for label, axis in [
            ("U_H(I)", SensorStudyAxis.CURRENT),
            ("U_H(d)", SensorStudyAxis.THICKNESS),
            ("U_H(α)", SensorStudyAxis.ANGLE),
        ]:
            selector.addItem(label, axis)
        study_layout.addWidget(selector)
        self.study_plot = SensorStudyPlot()
        self.study_plot.set_theme(theme)
        study_layout.addWidget(self.study_plot)

        def change():
            axis = selector.currentData()
            if axis is SensorStudyAxis.ANGLE:
                x = np.linspace(0, 360, 361)
                y = 0.1 * np.cos(np.deg2rad(x))
                unit = "°"
            elif axis is SensorStudyAxis.CURRENT:
                x = np.linspace(0, 20, 300)
                y = np.linspace(0, 0.1, 300)
                unit = "мА"
            else:
                x = np.linspace(0.05, 0.4, 300)
                y = np.linspace(0.1, 0.01, 300) ** 2
                unit = "мм"
            self.study_plot.set_curve(SensorStudyCurve(axis, x, y, unit))

        selector.currentIndexChanged.connect(change)
        selector.setCurrentIndex(2)
        self.tabs.addTab(study, "Исследование датчика")
        self.tabs.setCurrentIndex(
            {"visualization": 0, "experiment": 1, "sensor-study": 2}[mode]
        )

    def closeEvent(self, event):
        self.visualization.grid_timer.stop()
        for canvas in (
            self.visualization.canvas,
            self.experiment_canvas,
            self.study_canvas,
        ):
            canvas.shutdown()
        super().closeEvent(event)
