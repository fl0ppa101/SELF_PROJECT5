"""Integrate supplied vector samples only; no magnet model is present here."""

from dataclasses import dataclass
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsPathItem
from hallsim.core.contracts import FieldGrid
from .heatmap_layer import validate_grid


@dataclass(frozen=True)
class StreamlineGeometry:
    points_mm: np.ndarray


class GridSampler:
    """Bilinear interpolation with a conservative four-corner validity mask."""

    def __init__(self, grid):
        self.grid = grid
        self.x0, self.y0 = grid.x_mm[0], grid.y_mm[0]
        self.dx, self.dy = grid.x_mm[1] - self.x0, grid.y_mm[1] - self.y0
        self.nx, self.ny = len(grid.x_mm), len(grid.y_mm)
        self.valid = (
            grid.valid_mask
            & np.isfinite(grid.bx_mT)
            & np.isfinite(grid.by_mT)
            & np.isfinite(grid.modB_mT)
        )
        self.valid_cells = (
            self.valid[:-1, :-1]
            & self.valid[:-1, 1:]
            & self.valid[1:, :-1]
            & self.valid[1:, 1:]
        )

    def sample(self, points):
        p = np.asarray(points, dtype=float).reshape(-1, 2)
        u, v = (p[:, 0] - self.x0) / self.dx, (p[:, 1] - self.y0) / self.dy
        inside = (
            np.isfinite(p).all(axis=1)
            & (u >= 0)
            & (v >= 0)
            & (u <= self.nx - 1)
            & (v <= self.ny - 1)
        )
        i = np.clip(np.nan_to_num(u), 0, self.nx - 2).astype(int)
        j = np.clip(np.nan_to_num(v), 0, self.ny - 2).astype(int)
        ok = (
            inside
            & self.valid[j, i]
            & self.valid[j, i + 1]
            & self.valid[j + 1, i]
            & self.valid[j + 1, i + 1]
        )
        a, b = np.clip(u - i, 0, 1), np.clip(v - j, 0, 1)
        out = np.empty((len(p), 2))
        for k, data in enumerate((self.grid.bx_mT, self.grid.by_mT)):
            out[:, k] = (
                (1 - a) * (1 - b) * data[j, i]
                + a * (1 - b) * data[j, i + 1]
                + (1 - a) * b * data[j + 1, i]
                + a * b * data[j + 1, i + 1]
            )
        out[~ok] = np.nan
        return out, ok

    def direction(self, points):
        out, ok = self.sample(points)
        lengths = np.linalg.norm(out, axis=1)
        ok &= np.isfinite(lengths) & (lengths > 1e-12)
        out = out / np.where(ok, lengths, 1)[:, None]
        out[~ok] = 0
        return out, ok

    def segment_valid(self, start, end):
        # A step is shorter than half a grid cell. Test every cell in its bounding
        # rectangle, including near-corner crossings that point sampling can miss.
        origin, cell = np.array([self.x0, self.y0]), np.array([self.dx, self.dy])
        a = np.floor((start - origin) / cell).astype(int)
        b = np.floor((end - origin) / cell).astype(int)
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        inside = (lo >= 0).all(axis=1) & (hi < [self.nx - 1, self.ny - 1]).all(axis=1)
        lo = np.clip(lo, 0, [self.nx - 2, self.ny - 2])
        hi = np.clip(hi, 0, [self.nx - 2, self.ny - 2])
        return (
            inside
            & self.valid_cells[lo[:, 1], lo[:, 0]]
            & self.valid_cells[hi[:, 1], hi[:, 0]]
            & self.valid_cells[lo[:, 1], hi[:, 0]]
            & self.valid_cells[hi[:, 1], lo[:, 0]]
        )


class StreamlineBuilder:
    def build(
        self, grid: FieldGrid, *, density: float = 1.0, max_lines: int = 80
    ) -> list[StreamlineGeometry]:
        validate_grid(grid)
        if not np.isfinite(density) or density <= 0 or max_lines < 0:
            raise ValueError("density must be positive, max_lines nonnegative")
        if max_lines == 0:
            return []
        sampler = GridSampler(grid)
        width, height = np.ptp(grid.x_mm), np.ptp(grid.y_mm)
        spacing = max(width, height) / (16 * min(density, 4))
        sx = np.arange(grid.x_mm[0] + spacing / 2, grid.x_mm[-1], spacing)
        sy = np.arange(grid.y_mm[0] + spacing / 2, grid.y_mm[-1], spacing)
        xx, yy = np.meshgrid(sx, sy)
        seeds = np.column_stack((xx.ravel(), yy.ravel()))
        if not len(seeds):
            return []
        # Integrate all seeds in batches; half-cell steps cannot leap across a masked cell.
        step = 0.45 * min(sampler.dx, sampler.dy)
        steps = min(5000, int(3 * max(width, height) / step) + 1)
        branches = []
        for sign in (-1, 1):
            pos = seeds.copy()
            alive = np.ones(len(seeds), dtype=bool)
            histories = [[p.copy()] for p in seeds]
            for n in range(steps):
                ids = np.flatnonzero(alive)
                if not len(ids):
                    break
                start = pos[ids]
                d1, ok1 = sampler.direction(start)
                mid = start + sign * step / 2 * d1
                d2, ok2 = sampler.direction(mid)
                end = start + sign * step * d2
                _, ok3 = sampler.direction(end)
                ok = ok1 & ok2 & ok3
                ok &= sampler.segment_valid(start, end)
                alive[ids[~ok]] = False
                good = ids[ok]
                pos[good] = end[ok]
                for idx in good:
                    histories[idx].append(pos[idx].copy())
                if n > 20:
                    loop = np.linalg.norm(pos[good] - seeds[good], axis=1) < step * 1.2
                    alive[good[loop]] = False
            branches.append(histories)
        occupied = set()
        lines = []
        # Longest lines first; cell occupancy limits redundant neighboring traces.
        candidates = [np.asarray(left[:0:-1] + right) for left, right in zip(*branches)]
        candidates.sort(key=len, reverse=True)
        for points in candidates:
            if len(points) < 8:
                continue
            cells = set(
                map(
                    tuple,
                    np.floor(
                        (points - [sampler.x0, sampler.y0]) / (spacing * 0.55)
                    ).astype(int),
                )
            )
            if cells and len(cells & occupied) / len(cells) > 0.65:
                continue
            occupied.update(cells)
            lines.append(StreamlineGeometry(points))
            if len(lines) >= max_lines:
                break
        return lines


class _Signals(QObject):
    done = pyqtSignal(int, object, str)


class _BuildJob(QRunnable):
    def __init__(self, token, grid, density, max_lines):
        super().__init__()
        self.token, self.grid = token, grid
        self.density, self.max_lines = density, max_lines
        self.signals = _Signals()

    def run(self):
        try:
            result = StreamlineBuilder().build(
                self.grid, density=self.density, max_lines=self.max_lines
            )
            self.signals.done.emit(self.token, result, "")
        except Exception as exc:
            self.signals.done.emit(self.token, [], str(exc))


class StreamlineLayer(QObject):
    updated = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, plot, parent=None):
        super().__init__(parent)
        self.item = QGraphicsPathItem()
        self.item.setZValue(-10)
        plot.addItem(self.item)
        self.arrow_item = QGraphicsPathItem()
        self.arrow_item.setZValue(-9)
        plot.addItem(self.arrow_item)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._start)
        self.token = 0
        self.running = None
        self.pending = None
        self.mode = "full"
        self.density = 1.0
        self.geometry = []
        self.set_color("#e4f5ef")

    def set_color(self, color):
        c = QColor(color)
        c.setAlpha(105)
        self.item.setPen(pg.mkPen(c, width=0.85))
        c.setAlpha(165)
        self.arrow_item.setPen(pg.mkPen(c, width=0.9))
        self.arrow_item.setBrush(c)

    def set_visible(self, visible):
        self.item.setVisible(visible)
        self.arrow_item.setVisible(visible)

    def request(self, grid):
        self.token += 1
        self.pending = None if grid is None else (self.token, grid)
        if grid is None:
            self.geometry = []
            self.item.setPath(QPainterPath())
            self.arrow_item.setPath(QPainterPath())
        elif self.running is None and not self.timer.isActive():
            self.timer.start(150 if self.mode == "drag" else 0)

    def _start(self):
        if self.running is not None or self.pending is None:
            return
        token, grid = self.pending
        self.pending = None
        self.running = _BuildJob(
            token,
            grid,
            self.density * (0.75 if self.mode == "drag" else 1.1),
            24 if self.mode == "drag" else 40,
        )
        self.running.signals.done.connect(self._finished)
        self.pool.start(self.running)

    def _finished(self, token, geometry, error):
        self.running = None
        if token == self.token:
            if error:
                self.failed.emit(error)
            self.geometry = geometry
            self._draw(geometry)
            self.updated.emit()
        if self.pending is not None:
            self.timer.start(150 if self.mode == "drag" else 0)

    def _draw(self, geometry):
        path, arrows = QPainterPath(), QPainterPath()
        for line in geometry:
            pts = line.points_mm
            path.moveTo(*map(float, pts[0]))
            for pt in pts[1:]:
                path.lineTo(*map(float, pt))
            distance = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
            for s in np.arange(12.0, distance[-1] - 2, 26.0):
                i = min(np.searchsorted(distance, s), len(pts) - 1)
                d = pts[i] - pts[i - 1]
                d /= max(np.linalg.norm(d), 1e-12)
                normal = np.array([-d[1], d[0]])
                tip, base = pts[i], pts[i] - 1.4 * d
                arrows.moveTo(*map(float, tip))
                arrows.lineTo(*map(float, base + 0.5 * normal))
                arrows.lineTo(*map(float, base - 0.5 * normal))
                arrows.closeSubpath()
        self.item.setPath(path)
        self.arrow_item.setPath(arrows)

    def shutdown(self):
        self.timer.stop()
        self.pending = None
        self.token += 1
        self.pool.waitForDone()
