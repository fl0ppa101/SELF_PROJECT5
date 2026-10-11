"""PyQt6 / PyQtGraph views; no dependency on app or physics."""

from .field_canvas import FieldCanvas
from .path_plot import PathProfilePlot
from .streamline_layer import StreamlineBuilder, StreamlineGeometry

__all__ = ["FieldCanvas", "PathProfilePlot", "StreamlineBuilder", "StreamlineGeometry"]
