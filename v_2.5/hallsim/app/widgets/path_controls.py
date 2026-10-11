from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QToolButton,
)


class PathControls(QWidget):
    pathEdited = pyqtSignal(float, float, float, float)
    clearRequested = pyqtSignal()
    samplesEdited = pyqtSignal(int)

    def __init__(self, parent=None, *, samples=False):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        self.toggle = QToolButton()
        self.toggle.setText("Координаты A–B")
        self.toggle.setCheckable(True)
        self.clear_button = QPushButton("Убрать путь")
        self.clear_button.clicked.connect(self.clearRequested)
        bar.addWidget(self.toggle)
        bar.addStretch(1)
        bar.addWidget(self.clear_button)
        root.addLayout(bar)
        self.details = QWidget()
        form = QGridLayout(self.details)
        form.setContentsMargins(0, 0, 0, 0)
        self.coordinates = []
        for row, name in enumerate(("A", "B")):
            form.addWidget(QLabel(name), row, 0)
            for col, (axis, extent) in enumerate((("X", 80), ("Y", 50))):
                control = QDoubleSpinBox()
                control.setDecimals(2)
                control.setRange(-extent, extent)
                control.setSuffix(" мм")
                control.setKeyboardTracking(False)
                form.addWidget(QLabel(axis), row, 1 + col * 2)
                form.addWidget(control, row, 2 + col * 2)
                self.coordinates.append(control)
        self.apply_button = QPushButton("Применить путь")
        self.apply_button.clicked.connect(
            lambda: self.pathEdited.emit(*(c.value() for c in self.coordinates))
        )
        form.addWidget(self.apply_button, 2, 0, 1, 5)
        self.samples = None
        if samples:
            self.samples = QSpinBox()
            self.samples.setRange(2, 5000)
            self.samples.setKeyboardTracking(False)
            self.samples.editingFinished.connect(
                lambda: self.samplesEdited.emit(self.samples.value())
            )
            form.addWidget(QLabel("Точек профиля"), 3, 0, 1, 2)
            form.addWidget(self.samples, 3, 2, 1, 3)
        root.addWidget(self.details)
        self.details.hide()
        self.toggle.toggled.connect(self.details.setVisible)

    def refresh(self, path, locked=False):
        self.setEnabled(not locked)
        self.clear_button.setEnabled(path.enabled and not locked)
        values = (path.ax_mm, path.ay_mm, path.bx_mm, path.by_mm)
        for control, value in zip(self.coordinates, values):
            if not control.hasFocus():
                blocker = QSignalBlocker(control)
                control.setValue(value)
                del blocker
        if self.samples is not None:
            blocker = QSignalBlocker(self.samples)
            self.samples.setValue(path.samples)
            del blocker
