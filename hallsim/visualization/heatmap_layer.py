"""Immutable source arrays, explicit row-major geometry and invertible color scale."""
from dataclasses import dataclass
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QWidget
from hallsim.core.contracts import FieldGrid, ViewSettings
from .theme import get_theme


def enum_name(value):
    return value.name if hasattr(value, "name") else str(value).upper()


def validate_grid(grid: FieldGrid) -> None:
    x, y = np.asarray(grid.x_mm), np.asarray(grid.y_mm)
    for axis in (x, y):
        if axis.ndim != 1 or len(axis) < 2 or not np.all(np.isfinite(axis)):
            raise ValueError("Grid axes must have at least two finite coordinates")
        delta = np.diff(axis)
        if not np.all(delta > 0) or not np.allclose(delta, delta[0], rtol=1e-5):
            raise ValueError("ImageItem requires ascending, uniformly spaced axes")
    for name in ("bx_mT", "by_mT", "modB_mT", "valid_mask"):
        if np.shape(getattr(grid, name)) != (len(y), len(x)):
            raise ValueError(f"{name} must have shape (ny, nx)")


@dataclass(frozen=True)
class ColorScale:
    minimum: float
    maximum: float
    normalization: str
    gamma: float = 0.5

    def forward(self, values):
        a = np.asarray(values, dtype=float)
        if self.normalization == "LOG":
            # Nonpositive magnitudes cannot be represented on a logarithmic scale.
            safe = np.where(a > 0, np.clip(a, self.minimum, self.maximum), np.nan)
            return (np.log(safe) - np.log(self.minimum)) / (np.log(self.maximum) - np.log(self.minimum))
        z = np.clip((a - self.minimum) / (self.maximum - self.minimum), 0, 1)
        return z ** self.gamma if self.normalization == "POWER" else z

    def inverse(self, fractions):
        z = np.asarray(fractions, dtype=float)
        if self.normalization == "LOG":
            return np.exp(np.log(self.minimum) + z * (np.log(self.maximum) - np.log(self.minimum)))
        if self.normalization == "POWER":
            z = z ** (1 / self.gamma)
        return self.minimum + z * (self.maximum - self.minimum)


def color_scale(grid: FieldGrid | None, view: ViewSettings) -> ColorScale:
    mode, norm = enum_name(view.color_range_mode), enum_name(view.normalization)
    if norm not in {"LINEAR", "LOG", "POWER"}:
        raise ValueError("Unknown normalization")
    if not np.isfinite(view.power_gamma) or view.power_gamma <= 0:
        raise ValueError("power_gamma must be positive and finite")
    if not 90 <= view.percentile_clip <= 100:
        raise ValueError("percentile_clip must be in [90, 100]")
    values = np.empty(0)
    if grid is not None:
        data = np.asarray(grid.modB_mT)
        mask = np.asarray(grid.valid_mask, dtype=bool) & np.isfinite(data) & (data >= 0)
        if norm == "LOG":
            mask &= data > 0
        values = data[mask]
    if mode == "MANUAL":
        lo, hi = view.color_min_mT, view.color_max_mT
        if lo is None or hi is None or not np.isfinite([lo, hi]).all() or lo < 0 or hi <= lo:
            raise ValueError("Manual range must satisfy 0 <= min < max, with finite limits")
        if norm == "LOG" and lo <= 0:
            raise ValueError("Log range requires min > 0")
    elif mode in {"AUTO_PERCENTILE", "AUTO_FULL"}:
        if values.size:
            lo = float(values.min())
            hi = float(np.percentile(values, view.percentile_clip)) if mode == "AUTO_PERCENTILE" else float(values.max())
            if hi <= lo:
                if norm == "LOG":
                    lo, hi = lo / 2, lo * 2
                else:
                    lo, hi = 0., max(hi, 1.)
        else:
            lo, hi = (1e-3, 1.) if norm == "LOG" else (0., 1.)
    else:
        raise ValueError("Unknown color range mode")
    return ColorScale(float(lo), float(hi), norm, float(view.power_gamma))


def palette(name: str) -> np.ndarray:
    if name.lower() == "hall":
        colors = ["#193e87", "#276cb0", "#47bbc7", "#a3d7a2", "#f4de58", "#f89934", "#d82728", "#940d29"]
        cmap = pg.ColorMap(np.linspace(0, 1, len(colors)), [QColor(c) for c in colors])
    elif name.lower() in {"viridis", "turbo"}:
        cmap = pg.colormap.get(name.lower())
    else:
        raise ValueError("palette must be hall, viridis or turbo")
    return cmap.getLookupTable(0, 1, 256, alpha=True)


class ColorBar(QWidget):
    """Ticks are physical values at inverse-normalized gradient positions."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(96)
        self.scale = ColorScale(0, 1, "POWER")
        self.lut = palette("hall")
        self.theme = get_theme("light")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QColor(self.theme.foreground))
        p.drawText(QRectF(4, 8, 90, 24), Qt.AlignmentFlag.AlignLeft, "|B|, мТл")
        box = QRectF(8, 44, 16, max(40, self.height() - 106))
        grad = QLinearGradient(box.bottomLeft(), box.topLeft())
        for i in range(0, 256, 5):
            grad.setColorAt(i / 255, QColor(*map(int, self.lut[i])))
        grad.setColorAt(1, QColor(*map(int, self.lut[-1])))
        p.fillRect(box, grad)
        p.setPen(QPen(QColor(self.theme.border), 1))
        p.drawRect(box)
        p.setPen(QColor(self.theme.foreground))
        for fraction, value in zip(np.linspace(0, 1, 6), self.scale.inverse(np.linspace(0, 1, 6))):
            y = box.bottom() - fraction * box.height()
            p.drawLine(int(box.right()), int(y), int(box.right() + 4), int(y))
            p.drawText(QRectF(32, y - 10, 62, 20), Qt.AlignmentFlag.AlignVCenter, f"{value:.3g}")
        p.setPen(QColor(self.theme.muted))
        p.drawText(QRectF(5, box.bottom() + 18, 85, 28), Qt.AlignmentFlag.AlignLeft, self.scale.normalization.title())


class HeatmapLayer:
    def __init__(self, plot, colorbar: ColorBar):
        self.image = pg.ImageItem(axisOrder="row-major")
        self.image.setZValue(-20)
        plot.addItem(self.image)
        self.colorbar = colorbar
        self.grid = None
        self.view = ViewSettings()
        self.scale = color_scale(None, self.view)
        self.set_palette("hall")

    def set_palette(self, name: str):
        lut = palette(name)
        self.image.setLookupTable(lut)
        self.colorbar.lut = lut
        self.colorbar.update()

    def update(self, grid: FieldGrid | None, view: ViewSettings):
        if grid is not None:
            validate_grid(grid)
        self.scale = color_scale(grid, view)
        self.grid, self.view = grid, view
        self.colorbar.scale = self.scale
        self.colorbar.update()
        self.image.setVisible(view.show_heatmap and grid is not None)
        if grid is None:
            self.image.clear()
            return
        # Always use the ENTIRE array. Never feed viewport bounds to normalization.
        values = np.where(grid.valid_mask, grid.modB_mT, np.nan)
        values = np.where(np.isfinite(values) & (values >= 0), values, np.nan)
        data = np.ascontiguousarray(self.scale.forward(values), dtype=np.float32)
        self.image.setImage(data, autoLevels=False, levels=(0, 1))
        dx, dy = grid.x_mm[1] - grid.x_mm[0], grid.y_mm[1] - grid.y_mm[0]
        # x/y locate sample CENTERS, not the outer pixel edges.
        self.image.setRect(QRectF(grid.x_mm[0] - dx / 2, grid.y_mm[0] - dy / 2,
                                 len(grid.x_mm) * dx, len(grid.y_mm) * dy))
