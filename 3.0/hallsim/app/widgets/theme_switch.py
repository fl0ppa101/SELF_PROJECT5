from __future__ import annotations

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QPointF,
    QRectF,
    Qt,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QAbstractButton, QWidget


def _mix(start: QColor, end: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        round(start.red() + (end.red() - start.red()) * amount),
        round(start.green() + (end.green() - start.green()) * amount),
        round(start.blue() + (end.blue() - start.blue()) * amount),
        round(start.alpha() + (end.alpha() - start.alpha()) * amount),
    )


class AnimatedThemeSwitch(QAbstractButton):
    """Compact, keyboard-accessible light/dark switch drawn as one widget."""

    themeRequested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = "light"
        self._progress = 0.0
        self.setFixedSize(112, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Переключить светлую и тёмную тему")
        self.setAccessibleName("Тема оформления")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._animation = QPropertyAnimation(self, b"progress", self)
        self._animation.setDuration(320)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.clicked.connect(self._request_toggle)

    @property
    def theme(self) -> str:
        return self._theme

    @pyqtProperty(float)
    def progress(self) -> float:
        return self._progress

    @progress.setter
    def progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    def _request_toggle(self) -> None:
        self.themeRequested.emit("dark" if self._theme == "light" else "light")

    def set_theme(self, theme: str, *, animated: bool = True) -> None:
        if theme not in {"light", "dark"}:
            raise ValueError("Тема должна быть light или dark")
        self._theme = theme
        target = 1.0 if theme == "dark" else 0.0
        self.setAccessibleDescription(
            "Тёмная тема" if theme == "dark" else "Светлая тема"
        )
        self._animation.stop()
        if animated:
            self._animation.setStartValue(self._progress)
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self.progress = target

    def paintEvent(self, event) -> None:  # noqa: ARG002 - Qt event signature
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track = _mix(QColor("#eadfd4"), QColor("#252c35"), self._progress)
        border = _mix(QColor("#cdbcae"), QColor("#4a5663"), self._progress)
        knob_top = _mix(QColor("#fffdfa"), QColor("#f2b66f"), self._progress)
        knob_bottom = _mix(QColor("#fff5e9"), QColor("#d9855f"), self._progress)
        muted_icon = _mix(QColor("#997b6e"), QColor("#84909c"), self._progress)

        track_rect = QRectF(1.0, 1.0, self.width() - 2.0, self.height() - 2.0)
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(track)
        painter.drawRoundedRect(track_rect, 18.0, 18.0)

        self._draw_sun(painter, QPointF(20.0, 19.0), muted_icon, 0.65)
        self._draw_moon(painter, QPointF(self.width() - 20.0, 19.0), muted_icon, 0.72)

        knob_x = 4.0 + (self.width() - 38.0) * self._progress
        knob_rect = QRectF(knob_x, 4.0, 30.0, 30.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(19, 25, 31, 45 if not self.underMouse() else 65))
        painter.drawEllipse(knob_rect.translated(0.0, 1.5))

        gradient = QLinearGradient(knob_rect.topLeft(), knob_rect.bottomLeft())
        gradient.setColorAt(0.0, knob_top)
        gradient.setColorAt(1.0, knob_bottom)
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(255, 255, 255, 105), 1.0))
        painter.drawEllipse(knob_rect)

        if self._progress < 0.5:
            self._draw_sun(painter, knob_rect.center(), QColor("#9b4d32"), 1.0)
        else:
            self._draw_moon(painter, knob_rect.center(), QColor("#44302b"), 1.0)

        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(_mix(QColor("#8c493b"), QColor("#e89a7d"), self._progress), 1.5)
            )
            painter.drawRoundedRect(
                track_rect.adjusted(1.5, 1.5, -1.5, -1.5), 16.5, 16.5
            )

    @staticmethod
    def _draw_sun(
        painter: QPainter, center: QPointF, color: QColor, opacity: float
    ) -> None:
        painter.save()
        painter.setOpacity(opacity)
        painter.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, 4.1, 4.1)
        for dx, dy in (
            (0, -8),
            (0, 8),
            (-8, 0),
            (8, 0),
            (-5.7, -5.7),
            (5.7, 5.7),
            (-5.7, 5.7),
            (5.7, -5.7),
        ):
            inner = QPointF(center.x() + dx * 0.72, center.y() + dy * 0.72)
            outer = QPointF(center.x() + dx, center.y() + dy)
            painter.drawLine(inner, outer)
        painter.restore()

    @staticmethod
    def _draw_moon(
        painter: QPainter, center: QPointF, color: QColor, opacity: float
    ) -> None:
        painter.save()
        painter.setOpacity(opacity)
        painter.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.addEllipse(center, 7.0, 7.0)
        cutout = QPainterPath()
        cutout.addEllipse(QPointF(center.x() + 3.2, center.y() - 2.2), 6.1, 6.1)
        painter.setBrush(color)
        painter.drawPath(path.subtracted(cutout))
        painter.restore()
