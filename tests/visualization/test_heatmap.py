from dataclasses import replace
import numpy as np
import pyqtgraph as pg
import pytest
from PyQt6.QtCore import QPointF
from hallsim.core.contracts import ViewSettings
from hallsim.core.enums import ColorRangeMode, FieldNormalization
from hallsim.visualization.heatmap_layer import ColorBar, HeatmapLayer, color_scale, palette


def test_row_major_orientation_and_sample_centers(qapp, asymmetric_grid):
    plot = pg.PlotWidget()
    layer = HeatmapLayer(plot, ColorBar())
    settings = ViewSettings(normalization=FieldNormalization.LINEAR, color_range_mode=ColorRangeMode.AUTO_FULL)
    layer.update(asymmetric_grid, settings)
    assert layer.image.axisOrder == "row-major"
    np.testing.assert_allclose(layer.image.image, asymmetric_grid.modB_mT / 11)
    for j in range(3):
        for i in range(4):
            center = layer.image.mapToParent(QPointF(i+.5, j+.5))
            np.testing.assert_allclose([center.x(), center.y()], [asymmetric_grid.x_mm[i], asymmetric_grid.y_mm[j]])
    plot.close()


def test_range_modes_use_valid_finite_full_grid(asymmetric_grid):
    data = np.array(asymmetric_grid.modB_mT, copy=True)
    data[0, 0] = np.nan
    data[0, 1] = np.inf
    data[-1, -1] = 10000
    valid = asymmetric_grid.valid_mask.copy()
    valid[-1, -1] = False
    grid = replace(asymmetric_grid, modB_mT=data, valid_mask=valid)
    finite = data[valid & np.isfinite(data)]
    settings = ViewSettings()
    scale = color_scale(grid, settings)
    assert scale.minimum == finite.min()
    assert scale.maximum == pytest.approx(np.percentile(finite, 99.5))
    settings.color_range_mode = ColorRangeMode.AUTO_FULL
    assert color_scale(grid, settings).maximum == finite.max()
    settings.color_range_mode = ColorRangeMode.MANUAL
    settings.color_min_mT, settings.color_max_mT = 1., 30.
    assert (color_scale(grid, settings).minimum, color_scale(grid, settings).maximum) == (1., 30.)


@pytest.mark.parametrize("norm", list(FieldNormalization))
def test_normalization_and_colorbar_inverse(asymmetric_grid, norm):
    settings = ViewSettings(normalization=norm, color_range_mode=ColorRangeMode.MANUAL,
                            color_min_mT=.1, color_max_mT=40.)
    scale = color_scale(asymmetric_grid, settings)
    fractions = np.linspace(0, 1, 31)
    np.testing.assert_allclose(scale.forward(scale.inverse(fractions)), fractions, atol=1e-12)


@pytest.mark.parametrize("kind", ["zero", "nan", "masked", "none"])
@pytest.mark.parametrize("norm", list(FieldNormalization))
def test_empty_and_degenerate_grid_ranges(asymmetric_grid, norm, kind):
    grid = asymmetric_grid
    if kind == "none":
        grid = None
    elif kind == "zero":
        grid = replace(grid, modB_mT=np.zeros_like(grid.modB_mT))
    elif kind == "nan":
        grid = replace(grid, modB_mT=np.full_like(grid.modB_mT, np.nan))
    elif kind == "masked":
        grid = replace(grid, valid_mask=np.zeros_like(grid.valid_mask))
    scale = color_scale(grid, ViewSettings(normalization=norm))
    assert np.isfinite([scale.minimum, scale.maximum]).all()
    assert scale.maximum > scale.minimum
    if norm == FieldNormalization.LOG:
        assert scale.minimum > 0


def test_normalization_does_not_mutate_arrays(qapp, asymmetric_grid):
    original = [a.copy() for a in (asymmetric_grid.bx_mT, asymmetric_grid.by_mT, asymmetric_grid.modB_mT, asymmetric_grid.valid_mask)]
    for a in (asymmetric_grid.bx_mT, asymmetric_grid.by_mT, asymmetric_grid.modB_mT, asymmetric_grid.valid_mask):
        a.flags.writeable = False
    plot = pg.PlotWidget()
    layer = HeatmapLayer(plot, ColorBar())
    for norm in FieldNormalization:
        layer.update(asymmetric_grid, ViewSettings(normalization=norm))
    for before, after in zip(original, (asymmetric_grid.bx_mT, asymmetric_grid.by_mT, asymmetric_grid.modB_mT, asymmetric_grid.valid_mask)):
        np.testing.assert_array_equal(before, after)
    plot.close()


def test_manual_validation(asymmetric_grid):
    settings = ViewSettings(color_range_mode=ColorRangeMode.MANUAL)
    with pytest.raises(ValueError):
        color_scale(asymmetric_grid, settings)
    settings.color_min_mT, settings.color_max_mT = 0, 10
    settings.normalization = FieldNormalization.LOG
    with pytest.raises(ValueError):
        color_scale(asymmetric_grid, settings)


@pytest.mark.parametrize("name", ["hall", "viridis", "turbo"])
def test_palettes_have_rgba_lut(qapp, name):
    assert palette(name).shape == (256, 4)
