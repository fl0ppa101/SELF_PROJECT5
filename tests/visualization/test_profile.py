import numpy as np
import pytest
from PyQt6.QtCore import QPointF
from hallsim.core.contracts import PathProfile
from hallsim.visualization.path_plot import PathProfilePlot


@pytest.fixture
def graph(qapp):
    plot = PathProfilePlot()
    plot.resize(800, 280)
    plot.show()
    qapp.processEvents()
    yield plot
    plot.close()
    qapp.processEvents()


def test_nan_and_invalid_mask_preserve_line_gaps_and_input(graph):
    values = np.array([.1, 1., np.nan, 5., 10.])
    mask = np.array([True, True, False, True, False])
    profile = PathProfile(np.arange(5.)*10, values, mask, 0)
    graph.set_profile(profile)
    x, y = graph.curve.getData()
    assert len(x) == 5
    np.testing.assert_allclose(y, [.1, 1., np.nan, 5., np.nan], equal_nan=True)
    assert graph.curve.opts["connect"] == "finite"
    np.testing.assert_allclose(values, [.1, 1., np.nan, 5., 10.], equal_nan=True)


def test_linear_log_and_nonpositive_samples(graph):
    profile = PathProfile(np.arange(5.), np.array([0., .1, 1., 10., 100.]), np.ones(5, bool), 0)
    graph.set_profile(profile)
    assert graph.y_scale == "linear"
    np.testing.assert_allclose(graph.curve.getData()[1], profile.modB_mT)
    graph.set_y_scale("log")
    np.testing.assert_allclose(graph.curve.getData()[1], [np.nan, -1., 0., 1., 2.], equal_nan=True)
    graph.set_y_scale("linear")
    np.testing.assert_allclose(graph.curve.getData()[1], profile.modB_mT)


def test_crosshair_in_log_uses_physical_millitesla(graph, qapp):
    graph.set_profile(PathProfile(np.array([0., 10., 20.]), np.array([.1, 1., 10.]), np.ones(3, bool), 0))
    graph.set_y_scale("log")
    qapp.processEvents()
    graph._mouse_moved((graph.plot.getViewBox().mapViewToScene(QPointF(20, 1)),))
    assert "10 мТл" in graph.tooltip.toPlainText()
    assert graph.cross_y.value() == pytest.approx(1)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_none_nan_and_zero_profiles(graph, theme):
    graph.set_theme(theme)
    graph.set_profile(None)
    assert graph.empty_label.isVisible()
    assert graph.profile is None
    for values in [np.full(4, np.nan), np.zeros(4)]:
        graph.set_profile(PathProfile(np.arange(4.), values, np.isfinite(values), 0))
        graph.set_y_scale("log")
        assert graph.empty_label.isVisible()
    graph.clear_with_message("Тест")
    assert graph.empty_label.toPlainText() == "Тест"
