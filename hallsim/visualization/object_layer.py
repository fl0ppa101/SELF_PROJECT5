"""Schematic object geometry in millimeters; selection never mutates SceneState."""
import math
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsObject
import pyqtgraph as pg
from .theme import get_theme


def local_point(x, y, cx, cy, angle_deg):
    a = math.radians(angle_deg)
    dx, dy = x-cx, y-cy
    return dx*math.cos(a) + dy*math.sin(a), -dx*math.sin(a) + dy*math.cos(a)


def rectangle_hit(x, y, cx, cy, angle_deg, width, height):
    u, v = local_point(x, y, cx, cy, angle_deg)
    return abs(u) <= width/2 and abs(v) <= height/2


class BodyItem(QGraphicsObject):
    def __init__(self, sensor=False):
        super().__init__()
        self.sensor = sensor
        self.selected = False
        self.theme = get_theme("light")
        self.setZValue(20 if sensor else 10)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def boundingRect(self):
        return QRectF(-13, -8, 26, 24)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(-5, -.9, 10, 1.8) if self.sensor else QRectF(-10, -4, 20, 8)
        if self.sensor:
            gradient = QLinearGradient(0, -.9, 0, .9)
            gradient.setColorAt(0, QColor("#7d8c99"))
            gradient.setColorAt(.5, QColor("#edf1ee"))
            gradient.setColorAt(1, QColor("#a3adb4"))
        else:
            gradient = QLinearGradient(-10, 0, 10, 0)
            gradient.setColorAt(0, QColor("#17479f"))
            gradient.setColorAt(.34, QColor("#3977bd"))
            gradient.setColorAt(.49, QColor("#9dacb7"))
            gradient.setColorAt(.51, QColor("#d59687"))
            gradient.setColorAt(.68, QColor("#df4940"))
            gradient.setColorAt(1, QColor("#b52331"))
        painter.setBrush(gradient)
        painter.setPen(pg.mkPen("#263d50" if self.sensor else "#f4e9d3", width=1.2))
        painter.drawRoundedRect(rect, .35, .35)
        if not self.sensor:
            painter.save()
            painter.scale(1, -1)
            font = QFont("Georgia")
            font.setPointSizeF(3.5)
            painter.setFont(font)
            painter.setPen(QColor("#fff8e8"))
            painter.drawText(QRectF(-10, -4, 10, 8), Qt.AlignmentFlag.AlignCenter, "S")
            painter.drawText(QRectF(0, -4, 10, 8), Qt.AlignmentFlag.AlignCenter, "N")
            painter.restore()
        if self.selected:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(pg.mkPen(self.theme.selection, width=1.3))
            painter.drawRoundedRect(rect.adjusted(-.6, -.6, .6, .6), .5, .5)
            painter.drawLine(QPointF(0, rect.top()+rect.height()+.6), QPointF(0, 12))
            painter.setBrush(QColor(self.theme.panel))
            painter.drawEllipse(QPointF(0, 12), 1.3, 1.3)

    def handle_world(self):
        return self.mapToParent(QPointF(0, 12))


class ObjectLayer:
    def __init__(self, plot):
        self.plot = plot
        self.magnets = {}
        self.sensor = BodyItem(sensor=True)
        plot.addItem(self.sensor)
        self.label = pg.TextItem(anchor=(0, 1))
        self.label.setZValue(30)
        plot.addItem(self.label)
        self.selection = None
        self.theme_name = "light"
        self.scene = None
        self.sensor.hide()
        self.label.hide()

    def set_scene(self, scene):
        self.scene = scene
        active = {m.id for m in scene.magnets if m.enabled}
        for mid in list(self.magnets):
            if mid not in active:
                self.plot.removeItem(self.magnets.pop(mid))
        for magnet in scene.magnets:
            if not magnet.enabled:
                continue
            item = self.magnets.get(magnet.id)
            if item is None:
                item = self.magnets[magnet.id] = BodyItem()
                self.plot.addItem(item)
            item.setPos(magnet.x_mm, magnet.y_mm)
            item.setRotation(magnet.angle_deg)
        self.sensor.show()
        self.label.show()
        sensor = scene.sensor
        self.sensor.setPos(sensor.x_mm, sensor.y_mm)
        self.sensor.setRotation(sensor.angle_deg - 90)
        self.label.setPos(sensor.x_mm + 4, sensor.y_mm + 4)
        self.label.setText(f"Датчик Холла\nX = {sensor.x_mm:.1f} мм   Y = {sensor.y_mm:.1f} мм", color=get_theme(self.theme_name).foreground)
        if self.selection and self.selection[0] == "magnet" and self.selection[1] not in active:
            self.selection = None
        self.set_selection(self.selection)

    def set_selection(self, selection):
        self.selection = selection
        for mid, item in self.magnets.items():
            item.selected = selection == ("magnet", mid)
            item.theme = get_theme(self.theme_name)
            item.update()
        self.sensor.selected = selection == ("sensor", -1)
        self.sensor.theme = get_theme(self.theme_name)
        self.sensor.update()

    def set_theme(self, name):
        self.theme_name = name
        self.label.setColor(get_theme(name).foreground)
        self.label.fill = pg.mkBrush(get_theme(name).panel)
        self.label.update()
        self.label.setOpacity(.91)
        self.set_selection(self.selection)

    def hit_test(self, x, y, screen_distance):
        if self.scene is None:
            return None
        if self.selection:
            kind, mid = self.selection
            item = self.sensor if kind == "sensor" else self.magnets.get(mid)
            if item is not None:
                h = item.handle_world()
                if screen_distance(x, y, h.x(), h.y()) <= 9:
                    return (kind + "_rotation", mid)
        s = self.scene.sensor
        # At least a 5 px half-thickness for a usable sensor target.
        pixels_per_mm = max(screen_distance(x, y, x+1, y), 1e-6)
        if rectangle_hit(x, y, s.x_mm, s.y_mm, s.angle_deg-90, 10, max(1.8, 10/pixels_per_mm)):
            return ("sensor", -1)
        for m in reversed(self.scene.magnets):
            if m.enabled and rectangle_hit(x, y, m.x_mm, m.y_mm, m.angle_deg, 20, 8):
                return ("magnet", m.id)
        return None
