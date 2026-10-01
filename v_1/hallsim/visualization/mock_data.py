"""Procedural visual fixtures. These are NOT simulated magnetic fields.

Smooth stream-function derivatives provide loop-shaped test vectors; Gaussian
textures supply a useful dynamic range. No dipole formula or PhysicsEngine is used.
"""
import numpy as np
from hallsim.core.contracts import FieldGrid, FieldPoint, MagnetState, PathProfile, PathState, SceneState, SensorReading, SensorState, ViewSettings
from hallsim.core.enums import FieldStatus, SensorOrientationMode


def mock_scene(scenario="single_magnet") -> SceneState:
    if scenario == "single_magnet":
        magnets = [MagnetState(1, True, 0., 0., 0., "mock")]
    elif scenario in {"like_poles", "opposite_poles"}:
        magnets = [MagnetState(1, True, -30., 0., 0., "mock"),
                   MagnetState(2, True, 30., 0., 180. if scenario == "like_poles" else 0., "mock")]
    else:
        raise ValueError("Unknown mock scenario")
    return SceneState(magnets, SensorState(0., 30., 0., SensorOrientationMode.AUTO),
                      PathState(False, -70., 0., 70., 0.), ViewSettings())


def mock_grid(scene: SceneState, quality="full") -> FieldGrid:
    nx, ny = (320, 200) if quality == "drag" else (640, 400)
    x, y = np.linspace(-80., 80., nx), np.linspace(-50., 50., ny)
    xx, yy = np.meshgrid(x, y)
    bx, by = np.zeros_like(xx), np.zeros_like(xx)
    texture = np.zeros_like(xx)
    valid = np.ones_like(xx, dtype=bool)
    for m in scene.magnets:
        if not m.enabled:
            continue
        angle = np.deg2rad(m.angle_deg)
        c, s = np.cos(angle), np.sin(angle)
        u = (xx-m.x_mm)*c + (yy-m.y_mm)*s
        v = -(xx-m.x_mm)*s + (yy-m.y_mm)*c
        envelope = np.exp(-(u/38.)**2 - (v/34.)**2)
        t = np.tanh(v/9.)
        du = envelope*((1-t*t)/9. - 2*v*t/34.**2)
        dv = envelope*2*u*t/38.**2
        bx += du*c - dv*s
        by += du*s + dv*c
        texture += .13 + 6*np.exp(-(u/35)**2-(v/27)**2)
        for pole in (-10., 10.):
            texture += 34*np.exp(-((u-pole)/7.5)**2-(v/8.)**2)
        valid &= u*u + v*v >= .5**2
    direction_length = np.hypot(bx, by)
    factor = np.divide(texture, direction_length, out=np.zeros_like(texture), where=direction_length > 1e-12)
    bx, by = bx*factor, by*factor
    mod = np.hypot(bx, by)
    bx, by, mod = (np.where(valid, a, np.nan) for a in (bx, by, mod))
    return FieldGrid(x, y, bx, by, mod, valid, scene.revision)


def sample_fixture(grid, points):
    """Sample supplied mock arrays; require all four corners valid."""
    points = np.asarray(points).reshape(-1, 2)
    u = (points[:, 0]-grid.x_mm[0])/(grid.x_mm[1]-grid.x_mm[0])
    v = (points[:, 1]-grid.y_mm[0])/(grid.y_mm[1]-grid.y_mm[0])
    nx, ny = len(grid.x_mm), len(grid.y_mm)
    inside = (u >= 0) & (u <= nx-1) & (v >= 0) & (v <= ny-1)
    i, j = np.clip(u, 0, nx-2).astype(int), np.clip(v, 0, ny-2).astype(int)
    valid = inside & grid.valid_mask[j, i] & grid.valid_mask[j, i+1] & grid.valid_mask[j+1, i] & grid.valid_mask[j+1, i+1]
    a, b = np.clip(u-i, 0, 1), np.clip(v-j, 0, 1)
    result = []
    for values in (grid.bx_mT, grid.by_mT, grid.modB_mT):
        sampled = ((1-a)*(1-b)*values[j, i] + a*(1-b)*values[j, i+1]
                   + (1-a)*b*values[j+1, i] + a*b*values[j+1, i+1])
        result.append(np.where(valid & np.isfinite(sampled), sampled, np.nan))
    return result


def mock_profile(grid, path: PathState, revision):
    if not path.enabled:
        return None
    a, b = np.array([path.ax_mm, path.ay_mm]), np.array([path.bx_mm, path.by_mm])
    length = np.linalg.norm(b-a)
    if length < 1e-9:
        return None
    points = a + np.linspace(0, 1, path.samples)[:, None]*(b-a)
    values = sample_fixture(grid, points)[2]
    return PathProfile(np.linspace(0, length, path.samples), values, np.isfinite(values), revision)


def mock_reading(grid, sensor):
    bx, by, mod = [float(a[0]) for a in sample_fixture(grid, [[sensor.x_mm, sensor.y_mm]])]
    direction = float(np.degrees(np.arctan2(by, bx)) % 360) if np.isfinite(mod) and mod > 1e-6 else None
    status = FieldStatus.OK if direction is not None else (FieldStatus.ZERO_FIELD if np.isfinite(mod) else FieldStatus.INSIDE_SINGULARITY)
    # The demo readout is a fixture magnitude. Signed sensor physics belongs to module 01.
    return SensorReading(mod, FieldPoint(bx, by, mod, direction, status))
