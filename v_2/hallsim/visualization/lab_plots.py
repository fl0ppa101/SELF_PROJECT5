"""Plots display supplied arrays; all physical calculations stay outside."""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from hallsim.core.enums import MeasurementSource, SensorStudyAxis
from .theme import get_theme
from .axes import fixed_units_axis


class _LabPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(190)
        self.graphics = pg.PlotWidget()
        self.plot = self.graphics.getPlotItem()
        self.plot.hideButtons()
        self.plot.setMenuEnabled(False)
        self.plot.showGrid(x=True, y=True, alpha=0.12)
        self.curve = pg.PlotDataItem(connect="finite", antialias=True)
        self.plot.addItem(self.curve)
        self.message = pg.TextItem(anchor=(0.5, 0.5))
        self.plot.addItem(self.message, ignoreBounds=True)
        self.cross_x = pg.InfiniteLine(angle=90)
        self.cross_y = pg.InfiniteLine(angle=0)
        self.tooltip = pg.TextItem(anchor=(0, 1))
        self.tooltip.setZValue(50)
        for item in (self.cross_x, self.cross_y, self.tooltip):
            self.plot.addItem(item, ignoreBounds=True)
            item.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.graphics)
        self.x = np.empty(0)
        self.y = np.empty(0)
        self._bottom_label = ""
        self._left_label = ""
        self._proxy = pg.SignalProxy(
            self.graphics.scene().sigMouseMoved, rateLimit=30, slot=self._hover
        )
        self.plot.getViewBox().sigRangeChanged.connect(self._position_message)
        self.graphics.scene().sigMouseHover.connect(
            lambda items: (
                self._hide_hover() if self.plot.getViewBox() not in items else None
            )
        )
        self.theme_name = "light"
        self.set_theme("light")

    def labels(self, bottom, left):
        self._bottom_label, self._left_label = bottom, left
        self.plot.setLabel("bottom", bottom)
        self.plot.setLabel("left", left)
        for name in ("bottom", "left"):
            fixed_units_axis(self.plot.getAxis(name))

    def set_theme(self, theme):
        self.theme_name = theme
        t = get_theme(theme)
        self.graphics.setBackground(t.panel)
        self.curve.setPen(pg.mkPen(t.accent, width=2))
        for name in ("bottom", "left"):
            axis = self.plot.getAxis(name)
            axis.setPen(pg.mkPen(t.border))
            axis.setTextPen(pg.mkPen(t.foreground))
        for item in (self.cross_x, self.cross_y):
            item.setPen(pg.mkPen(t.muted, style=Qt.PenStyle.DashLine))
        self.message.setColor(t.muted)
        self.tooltip.setColor(t.foreground)
        self.tooltip.fill = pg.mkBrush(t.panel)
        self.tooltip.border = pg.mkPen(t.border)

    def _position_message(self, *args):
        x, y = self.plot.getViewBox().viewRange()
        self.message.setPos(sum(x) / 2, sum(y) / 2)

    def clear_with_message(self, text):
        self.x, self.y = np.empty(0), np.empty(0)
        self.curve.clear()
        self.message.setText(text)
        self.message.show()
        self.plot.setRange(xRange=(0, 1), yRange=(0, 1))
        self._position_message()
        self._hide_hover()

    def _hide_hover(self):
        for item in (self.cross_x, self.cross_y, self.tooltip):
            item.hide()

    def _hover(self, args):
        pos = args[0]
        vb = self.plot.getViewBox()
        if not self.x.size or not vb.sceneBoundingRect().contains(pos):
            self._hide_hover()
            return
        world = vb.mapSceneToView(pos)
        index = int(np.argmin(abs(self.x - world.x())))
        if not np.isfinite(self.y[index]):
            self._hide_hover()
            return
        self.cross_x.setPos(float(self.x[index]))
        self.cross_y.setPos(float(self.y[index]))
        self.tooltip.setAnchor(
            (1, 1) if world.x() > sum(vb.viewRange()[0]) / 2 else (0, 1)
        )
        self.tooltip.setPos(world)
        self.tooltip.setText(self.tooltip_text(index))
        for item in (self.cross_x, self.cross_y, self.tooltip):
            item.show()


class ExperimentPlot(_LabPlot):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.comparison = None
        self.theory = pg.PlotDataItem(connect="finite", antialias=True)
        self.plot.addItem(self.theory)
        self.legend = self.plot.addLegend(offset=(10, 10))
        self.legend.addItem(self.curve, "Эксперимент")
        self.legend.addItem(self.theory, "Теория")
        self.labels("Расстояние вдоль A–B, мм", "|B|, мТл")
        self.set_theme("light")
        self.clear()

    def set_measurements(self, points):
        self.points = sorted(points, key=lambda p: p.s_mm)
        self._hide_hover()
        self.x = np.array([p.s_mm for p in self.points])
        self.y = np.array([p.measured_modB_mT for p in self.points])
        size = 4 if len(points) > 100 else (9 if len(points) <= 20 else 6)
        t = get_theme(self.theme_name)
        self.curve.setData(
            self.x,
            self.y,
            connect="finite",
            symbol="o",
            symbolSize=size,
            symbolPen=t.accent,
            symbolBrush=t.panel,
        )
        self.message.setVisible(not bool(points))
        self.plot.enableAutoRange()

    def set_comparison(self, comparison):
        self.comparison = comparison
        if comparison is None:
            self.theory.clear()
            self.legend.hide()
        else:
            p = comparison.theory_profile
            self.theory.setData(
                p.distance_mm,
                np.where(p.valid_mask, p.modB_mT, np.nan),
                connect="finite",
            )
            self.legend.show()

    def set_theme(self, theme):
        super().set_theme(theme)
        if hasattr(self, "theory"):
            self.theory.setPen(
                pg.mkPen(get_theme(theme).success, width=2, style=Qt.PenStyle.DashLine)
            )
            self.set_measurements(self.points)

    def clear(self):
        self.points = []
        self.set_comparison(None)
        self.clear_with_message("Проведите измерения на отрезке A–B")

    def tooltip_text(self, index):
        p = self.points[index]
        source = "ручной" if p.source is MeasurementSource.MANUAL else "автоматический"
        text = f"s = {p.s_mm:.3g} мм\n|B|изм = {p.measured_modB_mT:.4g} мТл\n|U_H|max = {p.max_abs_hall_voltage_mV:.4g} мВ\nИсточник: {source}"
        if self.comparison is not None:
            c = self.comparison
            text += f"\n|B|теор = {c.theoretical_at_measured_mT[index]:.4g} мТл\nΔ = {c.abs_error_mT[index]:.4g} мТл"
        return text


class SensorStudyPlot(_LabPlot):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.study_curve = None
        self.zero_line = pg.InfiniteLine(
            pos=0, angle=0, pen=pg.mkPen(get_theme("light").muted)
        )
        self.plot.addItem(self.zero_line)
        self.clear_with_message("Разместите датчик в допустимой точке")

    def set_curve(self, curve):
        self.study_curve = curve
        if curve is None:
            self.clear_with_message("Недопустимая точка датчика")
            return
        names = {
            SensorStudyAxis.CURRENT: "I",
            SensorStudyAxis.THICKNESS: "d",
            SensorStudyAxis.ANGLE: "α",
        }
        self.labels(f"{names[curve.axis]}, {curve.x_unit}", "U_H, мВ")
        self.x = np.array(curve.x_values, copy=True)
        self.y = np.array(curve.hall_voltage_mV, copy=True)
        self.curve.setData(self.x, self.y, connect="finite")
        self.message.setVisible(not np.isfinite(self.y).any())
        self.plot.enableAutoRange()
        self._hide_hover()

    def set_theme(self, theme):
        super().set_theme(theme)
        if hasattr(self, "zero_line"):
            self.zero_line.setPen(pg.mkPen(get_theme(theme).muted))

    def tooltip_text(self, index):
        names = {
            SensorStudyAxis.CURRENT: "I",
            SensorStudyAxis.THICKNESS: "d",
            SensorStudyAxis.ANGLE: "α",
        }
        c = self.study_curve
        return f"{names[c.axis]} = {self.x[index]:.4g} {c.x_unit}\nU_H = {self.y[index]:.4g} мВ"
