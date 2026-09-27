"""Геометрия отрезка A-B и профиль магнитного поля."""

import numpy as np
from numpy.typing import NDArray

from hallsim.core.contracts import MagnetDefinition, MagnetState, PathProfile, PathState

from .field import field_components_at_points
from .validation import finite_real, positive_real, sample_count


def sample_segment(
    path: PathState,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    """Вернуть (x, y, расстояние от A) в мм, включая оба конца отрезка."""
    if not isinstance(path, PathState):
        raise ValueError("path must be a PathState")
    samples = sample_count(path.samples, "samples")
    ax = finite_real(path.ax_mm, "Coordinates: ax_mm")
    ay = finite_real(path.ay_mm, "Coordinates: ay_mm")
    bx = finite_real(path.bx_mm, "Coordinates: bx_mm")
    by = finite_real(path.by_mm, "Coordinates: by_mm")
    length_mm = np.hypot(bx - ax, by - ay)

    if length_mm == 0:
        raise ValueError("A and B must not be the same point")
    finite_real(length_mm, "path length")

    t = np.linspace(0, 1, samples)
    x_mm = ax + t * (bx - ax)
    y_mm = ay + t * (by - ay)
    distance_mm = t * length_mm

    return x_mm, y_mm, distance_mm


def compute_path_profile(
    magnets: list[MagnetState],
    magnet_catalog: dict[str, MagnetDefinition],
    path: PathState,
    *,
    scene_revision: int,
    singularity_radius_mm: float,
) -> PathProfile:
    """Профиль |B| в мТл вдоль A-B. Вызов не зависит от path.enabled."""
    radius = positive_real(singularity_radius_mm, "singularity_radius_mm")
    x, y, distance = sample_segment(path)
    bx, by, valid = field_components_at_points(
        magnets, magnet_catalog, x, y, singularity_radius_mm=radius,
    )
    return PathProfile(
        distance_mm=distance, modB_mT=np.hypot(bx, by),
        valid_mask=valid, scene_revision=scene_revision,
    )
