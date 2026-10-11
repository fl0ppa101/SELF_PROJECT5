import numpy as np
import pyqtgraph as pg
from PyQt6.QtGui import QPainterPath
from PyQt6.QtWidgets import QGraphicsPathItem

from .streamline_layer import GridSampler


class VectorLayer:
    def __init__(self, plot):
        self.view_box = plot.getViewBox()
        self.item = QGraphicsPathItem()
        self.item.setZValue(-8)
        plot.addItem(self.item)
        self.set_color("#e4f5ef")

    def set_color(self, color):
        self.item.setPen(pg.mkPen(color, width=1.2))

    def update(self, grid, visible, magnets=()):
        self.item.setVisible(visible and grid is not None)
        if not visible or grid is None:
            return
        ranges = self.view_box.viewRange()
        unit = (ranges[0][1] - ranges[0][0]) / max(1, self.view_box.width())
        spacing = 42 * unit
        if not np.isfinite(spacing) or spacing <= 0:
            return
        low = np.maximum([ranges[0][0], ranges[1][0]], [grid.x_mm[0], grid.y_mm[0]])
        high = np.minimum([ranges[0][1], ranges[1][1]], [grid.x_mm[-1], grid.y_mm[-1]])
        xs = np.arange(np.ceil(low[0] / spacing) * spacing, high[0], spacing)
        ys = np.arange(np.ceil(low[1] / spacing) * spacing, high[1], spacing)
        xx, yy = np.meshgrid(xs, ys)
        points = np.column_stack((xx.ravel(), yy.ravel()))
        vectors, valid = GridSampler(grid).sample(points)
        lengths = np.linalg.norm(vectors, axis=1)
        valid &= np.isfinite(lengths) & (lengths > 1e-6)
        for magnet in magnets:
            if not magnet.enabled:
                continue
            a = np.deg2rad(magnet.angle_deg)
            dx, dy = points[:, 0] - magnet.x_mm, points[:, 1] - magnet.y_mm
            valid &= ~(
                (abs(dx * np.cos(a) + dy * np.sin(a)) < 12)
                & (abs(-dx * np.sin(a) + dy * np.cos(a)) < 6)
            )
        path = QPainterPath()
        for point, vector, length in zip(points[valid], vectors[valid], lengths[valid]):
            direction = vector / length
            normal = np.array([-direction[1], direction[0]])
            tail, tip = point - 9 * unit * direction, point + 9 * unit * direction
            path.moveTo(*map(float, tail))
            path.lineTo(*map(float, tip))
            for sign in (-1, 1):
                wing = tip - 5 * unit * direction + sign * 3 * unit * normal
                path.moveTo(*map(float, wing))
                path.lineTo(*map(float, tip))
        self.item.setPath(path)
