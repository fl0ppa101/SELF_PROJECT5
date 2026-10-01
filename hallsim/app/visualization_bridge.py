from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from hallsim.core.config import X_MAX_MM, X_MIN_MM, Y_MAX_MM, Y_MIN_MM


class MockFieldCanvas(QWidget):
    magnetDragStarted = pyqtSignal(int)
    magnetDragged = pyqtSignal(int, float, float)
    magnetDragFinished = pyqtSignal(int, float, float)
    magnetRotationStarted = pyqtSignal(int)
    magnetRotated = pyqtSignal(int, float)
    magnetRotationFinished = pyqtSignal(int, float)
    sensorDragStarted = pyqtSignal()
    sensorDragged = pyqtSignal(float, float)
    sensorDragFinished = pyqtSignal(float, float)
    sensorRotated = pyqtSignal(float)
    pathPointMoved = pyqtSignal(str, float, float)
    cursorWorldPositionChanged = pyqtSignal(float, float)
    objectSelected = pyqtSignal(str, int)
    viewTransformChanged = pyqtSignal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = None
        self._theme = "light"
        self._quality = "full"
        self.setMinimumSize(620, 390)
        self.setMouseTracking(True)
        self.setObjectName("fieldCanvas")

    def set_scene(self, scene) -> None:
        self._scene = scene
        self.update()

    def set_field_grid(self, grid) -> None:
        self.update()

    def set_sensor_reading(self, reading) -> None:
        self.update()

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self.update()

    def set_interaction_quality(self, mode: str) -> None:
        self._quality = mode

    def reset_view(self) -> None:
        self.viewTransformChanged.emit(1.0)

    def mouseMoveEvent(self, event) -> None:
        rect = self.rect().adjusted(54, 28, -28, -42)
        if rect.contains(event.position().toPoint()):
            x = X_MIN_MM + (event.position().x() - rect.left()) / rect.width() * (X_MAX_MM - X_MIN_MM)
            y = Y_MAX_MM - (event.position().y() - rect.top()) / rect.height() * (Y_MAX_MM - Y_MIN_MM)
            self.cursorWorldPositionChanged.emit(x, y)
        super().mouseMoveEvent(event)

    def _world(self, x_mm: float, y_mm: float, rect) -> QPointF:
        x = rect.left() + (x_mm - X_MIN_MM) / (X_MAX_MM - X_MIN_MM) * rect.width()
        y = rect.top() + (Y_MAX_MM - y_mm) / (Y_MAX_MM - Y_MIN_MM) * rect.height()
        return QPointF(x, y)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = self._theme == "dark"
        background_top = QColor("#111e29" if dark else "#edf5f6")
        background_bottom = QColor("#172633" if dark else "#e5eff1")
        grid = QColor(255, 255, 255, 30) if dark else QColor(40, 83, 96, 28)
        text = QColor("#dce7ec" if dark else "#43525a")
        rect = self.rect().adjusted(54, 28, -28, -42)
        background = QLinearGradient(
            float(rect.left()),
            float(rect.top()),
            float(rect.left()),
            float(rect.bottom()),
        )
        background.setColorAt(0.0, background_top)
        background.setColorAt(1.0, background_bottom)
        painter.fillRect(rect, background)
        painter.setPen(QPen(grid, 1))
        for index in range(11):
            x = rect.left() + rect.width() * index / 10
            painter.drawLine(int(x), rect.top(), int(x), rect.bottom())
        for index in range(9):
            y = rect.top() + rect.height() * index / 8
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))
        painter.setPen(QPen(QColor(text.red(), text.green(), text.blue(), 150), 1))
        painter.drawRect(rect)
        painter.drawText(rect.left(), rect.bottom() + 26, "X, мм")
        painter.save()
        painter.translate(18, rect.center().y())
        painter.rotate(-90)
        painter.drawText(0, 0, "Y, мм")
        painter.restore()

        if self._scene is not None:
            if self._scene.path.enabled:
                start = self._world(self._scene.path.ax_mm, self._scene.path.ay_mm, rect)
                end = self._world(self._scene.path.bx_mm, self._scene.path.by_mm, rect)
                painter.setPen(
                    QPen(
                        QColor("#f2c66d" if dark else "#9c6230"),
                        1.5,
                        Qt.PenStyle.DashLine,
                    )
                )
                painter.drawLine(start, end)
                painter.setBrush(QColor("#f2c66d" if dark else "#9c6230"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(start, 4.0, 4.0)
                painter.drawEllipse(end, 4.0, 4.0)
                painter.setPen(text)
                painter.drawText(start + QPointF(7.0, -7.0), "A")
                painter.drawText(end + QPointF(7.0, -7.0), "B")

            for magnet in self._scene.magnets:
                center = self._world(magnet.x_mm, magnet.y_mm, rect)
                painter.save()
                painter.setOpacity(1.0 if magnet.enabled else 0.35)
                painter.translate(center)
                painter.rotate(-magnet.angle_deg)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#3269c7"))
                painter.drawRoundedRect(QRectF(-35, -13, 70, 26), 5, 5)
                painter.fillRect(QRectF(0, -13, 35, 26), QColor("#d44d43"))
                painter.setPen(QPen(QColor(255, 255, 255, 120), 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(QRectF(-35, -13, 70, 26), 5, 5)
                painter.setFont(QFont(painter.font().family(), 9, QFont.Weight.DemiBold))
                painter.setPen(Qt.GlobalColor.white)
                painter.drawText(QRectF(-35, -13, 35, 26), Qt.AlignmentFlag.AlignCenter, "S")
                painter.drawText(QRectF(0, -13, 35, 26), Qt.AlignmentFlag.AlignCenter, "N")
                painter.restore()
            sensor = self._world(self._scene.sensor.x_mm, self._scene.sensor.y_mm, rect)
            painter.save()
            painter.translate(sensor)
            painter.rotate(-self._scene.sensor.angle_deg)
            painter.setPen(QPen(QColor("#20262a" if not dark else "#f1f5f7"), 2))
            painter.setBrush(QColor("#f7f9fa" if dark else "#28333a"))
            painter.drawRoundedRect(QRectF(-4, -17, 8, 34), 3, 3)
            painter.setPen(QPen(QColor("#d67c68"), 2))
            painter.drawLine(QPointF(0, -14), QPointF(0, -5))
            painter.restore()

        badge_text = "Предпросмотр · визуализатор не подключён"
        painter.setFont(QFont(painter.font().family(), 9))
        metrics = painter.fontMetrics()
        badge_width = metrics.horizontalAdvance(badge_text) + 22
        badge_rect = QRectF(
            rect.right() - badge_width - 10,
            rect.bottom() - 34,
            badge_width,
            24,
        )
        painter.setPen(QPen(QColor(255, 255, 255, 28) if dark else QColor(40, 72, 80, 25)))
        painter.setBrush(QColor(18, 27, 34, 180) if dark else QColor(255, 255, 255, 205))
        painter.drawRoundedRect(badge_rect, 12, 12)
        painter.setPen(QColor("#9ca9b2" if dark else "#687980"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)


class MockPathProfilePlot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(165)
        layout = QVBoxLayout(self)
        self._label = QLabel("Задайте путь A-B на карте")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setObjectName("emptyPlotLabel")
        layout.addWidget(self._label)

    def set_profile(self, profile) -> None:
        self._label.setText("Профиль |B|(s) получен")

    def set_y_scale(self, scale: str) -> None:
        self.setProperty("yScale", scale)

    def set_theme(self, theme: str) -> None:
        self.setProperty("theme", theme)

    def clear_with_message(self, text: str) -> None:
        self._label.setText(text)


def create_field_canvas(parent: QWidget | None = None) -> QWidget:
    try:
        from hallsim.visualization.field_canvas import FieldCanvas
    except ModuleNotFoundError as exc:
        if exc.name not in {"hallsim.visualization", "hallsim.visualization.field_canvas"}:
            raise
        return MockFieldCanvas(parent)
    return FieldCanvas(parent)


def create_path_profile_plot(parent: QWidget | None = None) -> QWidget:
    try:
        from hallsim.visualization.path_plot import PathProfilePlot
    except ModuleNotFoundError as exc:
        if exc.name not in {"hallsim.visualization", "hallsim.visualization.path_plot"}:
            raise
        return MockPathProfilePlot(parent)
    return PathProfilePlot(parent)
