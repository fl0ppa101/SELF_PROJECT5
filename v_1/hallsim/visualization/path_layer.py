import pyqtgraph as pg
from PyQt6.QtCore import Qt
from .theme import get_theme


class PathLayer:
    def __init__(self, plot):
        self.path = None
        self.line = pg.PlotDataItem()
        self.line.setZValue(5)
        plot.addItem(self.line)
        self.points = pg.ScatterPlotItem(size=11, pxMode=True)
        self.points.setZValue(40)
        plot.addItem(self.points)
        self.labels = [pg.TextItem(text=name, anchor=(.5, 1.6)) for name in ("A", "B")]
        for label in self.labels:
            label.setZValue(41)
            plot.addItem(label)
            label.hide()
        self.set_theme("light")

    def set_path(self, path):
        self.path = path
        visible = path is not None and path.enabled
        self.line.setVisible(visible)
        self.points.setVisible(visible)
        for label in self.labels:
            label.setVisible(visible)
        if visible:
            xs, ys = [path.ax_mm, path.bx_mm], [path.ay_mm, path.by_mm]
            self.line.setData(xs, ys)
            self.points.setData(xs, ys)
            for label, x, y in zip(self.labels, xs, ys):
                label.setPos(x, y)

    def set_theme(self, name):
        t = get_theme(name)
        self.line.setPen(pg.mkPen("#f7ecd9" if name == "light" else "#d1deeb", width=1.3, style=Qt.PenStyle.DashLine))
        self.points.setPen(pg.mkPen(t.selection, width=1.8))
        self.points.setBrush(pg.mkBrush(t.accent))
        for label in self.labels:
            label.setColor("#fff5e4" if name == "light" else "#e8f0ff")

    def hit_test(self, x, y, screen_distance):
        p = self.path
        if p is not None and p.enabled:
            for name, px, py in [("A", p.ax_mm, p.ay_mm), ("B", p.bx_mm, p.by_mm)]:
                if screen_distance(x, y, px, py) <= 10:
                    return ("path", name)
        return None
