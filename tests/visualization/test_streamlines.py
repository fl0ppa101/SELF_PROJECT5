from dataclasses import replace
import numpy as np
import pytest
from hallsim.core.contracts import FieldGrid
from hallsim.visualization.streamline_layer import GridSampler, StreamlineBuilder


def uniform_grid():
    x, y = np.linspace(-20., 20., 81), np.linspace(-10., 10., 41)
    one = np.ones((len(y), len(x)))
    return FieldGrid(x, y, one, one*0, one, one.astype(bool), 0)


def test_uniform_lines_are_continuous_and_directed_forward():
    lines = StreamlineBuilder().build(uniform_grid(), density=.8, max_lines=10)
    assert 0 < len(lines) <= 10
    for line in lines:
        delta = np.diff(line.points_mm, axis=0)
        assert np.all(delta[:, 0] > 0)
        np.testing.assert_allclose(delta[:, 1], 0, atol=1e-12)
        assert np.max(np.linalg.norm(delta, axis=1)) <= .5


def test_masked_vertical_barrier_is_never_crossed():
    grid = uniform_grid()
    mask = grid.valid_mask.copy()
    mask[:, 38:43] = False
    bx = np.where(mask, grid.bx_mT, np.nan)
    grid = replace(grid, bx_mT=bx, valid_mask=mask)
    sampler = GridSampler(grid)
    lines = StreamlineBuilder().build(grid, density=1., max_lines=30)
    assert lines
    for line in lines:
        assert np.all(line.points_mm[:, 0] < 0) or np.all(line.points_mm[:, 0] > 0)
        _, valid = sampler.sample(line.points_mm)
        assert valid.all()


def test_interpolation_rejects_nan_corner_even_when_mask_true():
    grid = uniform_grid()
    bx = grid.bx_mT.copy()
    bx[20, 40] = np.nan
    grid = replace(grid, bx_mT=bx)
    _, valid = GridSampler(grid).sample([[.1, .1], [10., 5.]])
    assert valid.tolist() == [False, True]


@pytest.mark.parametrize("kind", ["zero", "nan", "masked"])
def test_no_lines_for_invalid_or_zero_vectors(kind):
    grid = uniform_grid()
    if kind == "zero":
        grid = replace(grid, bx_mT=grid.bx_mT*0)
    elif kind == "nan":
        grid = replace(grid, by_mT=np.full_like(grid.by_mT, np.nan))
    else:
        grid = replace(grid, valid_mask=~grid.valid_mask)
    assert StreamlineBuilder().build(grid, density=1., max_lines=10) == []


def test_max_lines_and_density_validation():
    builder, grid = StreamlineBuilder(), uniform_grid()
    assert builder.build(grid, density=1, max_lines=0) == []
    with pytest.raises(ValueError):
        builder.build(grid, density=0, max_lines=10)
