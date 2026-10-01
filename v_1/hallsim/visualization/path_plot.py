"""Distance profile in mm/mT, with honest gaps and physical-unit crosshair."""
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from hallsim.core.contracts import PathProfile
from .theme import get_theme


class PathProfilePlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.graphics = pg.PlotWidget()
        self.plot = self.graphics.getPlotItem()
        self.plot.hideButtons()
        self.plot.setMenuEnabled(False)
        self.plot.setLabel("bottom", "Расстояние вдоль пути, мм")
        self.plot.setLabel("left", "|B|, мТл")
        for name in ("left", "bottom"):
            self.plot.getAxis(name).enableAutoSIPrefix(False)
        self.plot.showGrid(x=True, y=True, alpha=.12)
        self.curve = pg.PlotDataItem(connect="finite", antialias=True)
        self.plot.addItem(self.curve)
        self.empty_label = pg.TextItem(anchor=(.5, .5))
        self.empty_label.setZValue(10)
        self.plot.addItem(self.empty_label)
        self.cross_x = pg.InfiniteLine(angle=90, movable=False)
        self.cross_y = pg.InfiniteLine(angle=0, movable=False)
        self.tooltip = pg.TextItem(anchor=(0, 1))
        self.tooltip.setZValue(20)
        for item in (self.cross_x, self.cross_y, self.tooltip):
            self.plot.addItem(item, ignoreBounds=True)
            item.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.graphics)
        self.profile = None
        self.y_scale = "linear"
        self.theme_name = "light"
        self._display_values = np.empty(0)
        self.plot.getViewBox().sigRangeChanged.connect(self._position_message)
        self._mouse_proxy = pg.SignalProxy(self.graphics.scene().sigMouseMoved, rateLimit=30, slot=self._mouse_moved)
        self.graphics.scene().sigMouseHover.connect(self._mouse_hover)
        self.set_theme("light")
        self.clear_with_message("Задайте путь A–B на карте")

    def set_profile(self, profile: PathProfile | None) -> None:
        if profile is None:
            self.clear_with_message("Задайте путь A–B на карте")
            return
        x, y, mask = np.asarray(profile.distance_mm), np.asarray(profile.modB_mT), np.asarray(profile.valid_mask)
        if x.ndim != 1 or x.shape != y.shape or x.shape != mask.shape or not len(x):
            raise ValueError("Profile must contain equally sized, nonempty 1D arrays")
        self.profile = profile
        self.empty_label.hide()
        self.curve.show()
        self._refresh_curve()
        finite = np.isfinite(x) & np.isfinite(self._display_values)
        if np.any(finite):
            self.plot.getViewBox().enableAutoRange()
        else:
            self.empty_label.setText("Нет допустимых значений для выбранной шкалы")
            self.empty_label.show()
            self._position_message()

    def _refresh_curve(self):
        if self.profile is None:
            return
        p = self.profile
        valid = np.asarray(p.valid_mask, dtype=bool) & np.isfinite(p.modB_mT) & np.isfinite(p.distance_mm) & (p.modB_mT >= 0)
        if self.y_scale == "log":
            valid &= p.modB_mT > 0
        self._display_values = np.where(valid, p.modB_mT, np.nan)
        # Preserve the original index sequence: removing invalid samples would bridge gaps.
        self.curve.setData(np.array(p.distance_mm, copy=True), self._display_values, connect="finite")

    def set_y_scale(self, scale: str) -> None:
        name = scale.lower()
        if name not in {"linear", "log"}:
            raise ValueError("y scale must be linear or log")
        self.y_scale = name
        self.plot.setLogMode(x=False, y=name == "log")
        if self.profile is not None:
            self.set_profile(self.profile)
        self._hide_crosshair()

    def set_theme(self, theme: str) -> None:
        t = get_theme(theme)
        self.theme_name = theme
        self.graphics.setBackground(t.panel)
        self.curve.setPen(pg.mkPen(t.accent, width=2))
        for name in ("left", "bottom"):
            axis = self.plot.getAxis(name)
            axis.setPen(pg.mkPen(t.border))
            axis.setTextPen(pg.mkPen(t.foreground))
            axis.setLabel("|B|, мТл" if name == "left" else "Расстояние вдоль пути, мм", color=t.foreground)
        for line in (self.cross_x, self.cross_y):
            line.setPen(pg.mkPen(t.muted, width=1, style=Qt.PenStyle.DashLine))
        self.empty_label.setColor(t.muted)
        self.tooltip.setColor(t.foreground)
        self.tooltip.fill = pg.mkBrush(t.panel)
        self.tooltip.border = pg.mkPen(t.border)
        self.tooltip.update()

    def clear_with_message(self, text: str) -> None:
        self.profile = None
        self._display_values = np.empty(0)
        self.curve.clear()
        self.plot.getViewBox().setRange(xRange=(0, 1), yRange=(0, 1), padding=0)
        self.empty_label.setText(text)
        self.empty_label.show()
        self._hide_crosshair()
        self._position_message()

    def _position_message(self, *args):
        x, y = self.plot.getViewBox().viewRange()
        self.empty_label.setPos((x[0]+x[1])/2, (y[0]+y[1])/2)

    def _hide_crosshair(self):
        for item in (self.cross_x, self.cross_y, self.tooltip):
            item.hide()

    def reset_view(self):
        self.plot.getViewBox().enableAutoRange()

    def _mouse_hover(self, items):
        if self.plot.getViewBox() not in items:
            self._hide_crosshair()

    def _mouse_moved(self, args):
        pos = args[0]
        vb = self.plot.getViewBox()
        if self.profile is None or not vb.sceneBoundingRect().contains(pos):
            self._hide_crosshair()
            return
        world = vb.mapSceneToView(pos)
        distances = self.profile.distance_mm
        finite_x = np.isfinite(distances)
        if not np.any(finite_x):
            return
        delta = np.where(finite_x, abs(distances-world.x()), np.inf)
        index = int(np.argmin(delta))
        value = self._display_values[index]
        if not np.isfinite(value):
            self._hide_crosshair()
            return
        display_y = np.log10(value) if self.y_scale == "log" else value
        self.cross_x.setPos(float(distances[index]))
        self.cross_y.setPos(float(display_y))
        # Anchor to the left at the right side of the graph to avoid clipped labels.
        right_half = world.x() > sum(vb.viewRange()[0])/2
        self.tooltip.setAnchor((1, 1) if right_half else (0, 1))
        self.tooltip.setPos(world)
        self.tooltip.setText(f"s = {distances[index]:.2f} мм\n|B| = {value:.3g} мТл")
        for item in (self.cross_x, self.cross_y, self.tooltip):
            item.show()
