"""Measurement markers and geometry only; no experiment lifecycle or physics."""

import math
import numpy as np
import pyqtgraph as pg
from .theme import get_theme


def project_to_segment(path, x, y):
    dx, dy = path.bx_mm - path.ax_mm, path.by_mm - path.ay_mm
    length_squared = dx * dx + dy * dy
    if not path.enabled or length_squared <= 1e-12:
        return None
    t = float(
        np.clip(((x - path.ax_mm) * dx + (y - path.ay_mm) * dy) / length_squared, 0, 1)
    )
    return t * math.sqrt(length_squared), path.ax_mm + t * dx, path.ay_mm + t * dy


class ExperimentLayer:
    def __init__(self, plot):
        self.points = []
        self.pending = []
        self.active = None
        self.theme = "light"
        self.markers = pg.ScatterPlotItem(pxMode=True)
        self.markers.setZValue(6)
        self.preview = pg.ScatterPlotItem(pxMode=True, size=12, symbol="o")
        self.preview.setZValue(32)
        plot.addItem(self.markers)
        plot.addItem(self.preview)
        self.preview.hide()

    def refresh(self):
        t = get_theme(self.theme)
        spots = [
            dict(pos=(x, y), size=6, brush=t.muted, pen=None)
            for s, x, y in self.pending
        ]
        size = 5 if len(self.points) > 100 else (9 if len(self.points) <= 20 else 7)
        for point in self.points:
            valid = np.isfinite(point.measured_modB_mT)
            spots.append(
                dict(
                    pos=(point.x_mm, point.y_mm),
                    size=size,
                    symbol="o" if valid else "x",
                    brush=t.success if valid else t.invalid,
                    pen=pg.mkPen(t.success if valid else t.invalid, width=1.5),
                )
            )
        if self.active is not None:
            _, x, y = self.active
            spots.append(
                dict(
                    pos=(x, y),
                    size=16,
                    brush=pg.mkBrush(0, 0, 0, 0),
                    pen=pg.mkPen(t.accent, width=2),
                )
            )
        self.markers.setData(spots)
        self.preview.setPen(pg.mkPen(t.accent, width=1.5))
        self.preview.setBrush(pg.mkBrush(0, 0, 0, 0))

    def hit_test(self, x, y, screen_distance):
        for point in reversed(self.points):
            if screen_distance(x, y, point.x_mm, point.y_mm) <= 9:
                return point.s_mm
        return None
