import time
from PyQt6.QtTest import QSignalSpy
from hallsim.visualization.streamline_layer import StreamlineBuilder, StreamlineLayer
from hallsim.visualization.mock_data import mock_scene, mock_grid
import pyqtgraph as pg


def test_worker_keeps_only_latest_pending_and_discards_stale_result(qapp, monkeypatch):
    calls = []
    def slow_build(self, grid, *, density, max_lines):
        calls.append(grid.scene_revision)
        time.sleep(.035)
        return []
    monkeypatch.setattr(StreamlineBuilder, "build", slow_build)
    plot = pg.PlotWidget()
    layer = StreamlineLayer(plot)
    updated = QSignalSpy(layer.updated)
    scene = mock_scene()
    first = mock_grid(scene, "drag")
    layer.request(first)
    qapp.processEvents()
    assert layer.running is not None
    for rev in (1, 2, 3):
        scene.revision = rev
        layer.request(mock_grid(scene, "drag"))
    deadline = time.monotonic() + 2
    while layer.running is not None or layer.pending is not None or layer.timer.isActive():
        assert time.monotonic() < deadline
        qapp.processEvents()
        time.sleep(.005)
    assert calls == [0, 3]
    assert len(updated) == 1
    layer.shutdown()
    plot.close()
