"""Расчёт магнитного поля точечных диполей."""

import math

import numpy as np
from numpy.typing import NDArray

from hallsim.core.contracts import FieldGrid, FieldPoint, MagnetDefinition, MagnetState
from hallsim.core.enums import FieldStatus

from .validation import finite_real, positive_real, sample_count, validate_magnets


def dipole_field_si(
    dx_m: float | NDArray[np.float64],
    dy_m: float | NDArray[np.float64],
    moment_Am2: float,
    angle_deg: float,
) -> tuple[float | NDArray[np.float64], float | NDArray[np.float64]]:
    """Смещения в метрах; результат (Bx, By) в теслах. Требуется r > 0."""

    dx_m = np.asarray(dx_m, dtype=np.float64)
    dy_m = np.asarray(dy_m, dtype=np.float64)
    if dx_m.shape != dy_m.shape:
        raise ValueError("dx_m and dy_m must have the same shape")

    r = np.hypot(dx_m, dy_m)
    r_x = dx_m / r
    r_y = dy_m / r
    c = 1e-7 / r**3  # mu0 / (4*pi) ≈ 1e-7 в SI.

    angle_rad = math.radians(angle_deg)
    m_x = moment_Am2 * math.cos(angle_rad)
    m_y = moment_Am2 * math.sin(angle_rad)

    q = m_x * r_x + m_y * r_y
    Bx = c * (3 * q * r_x - m_x)
    By = c * (3 * q * r_y - m_y)

    if dx_m.ndim == 0:
        return float(Bx), float(By)
    return Bx, By


def field_components_at_points(
    magnets: list[MagnetState],
    magnet_catalog: dict[str, MagnetDefinition],
    x_mm: NDArray[np.float64],
    y_mm: NDArray[np.float64],
    *,
    singularity_radius_mm: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    """Координаты в мм; результат (Bx, By) в мТл и маска допустимости."""
    if x_mm.shape != y_mm.shape:
        raise ValueError("x_mm and y_mm must have the same shape")
    if not math.isfinite(singularity_radius_mm) or singularity_radius_mm <= 0:
        raise ValueError("singularity_radius_mm must be finite and positive")
    if not np.isfinite(x_mm).all() or not np.isfinite(y_mm).all():
        raise ValueError("coordinates must be finite")
    validate_magnets(magnets, magnet_catalog)

    bx_total_T = np.zeros_like(x_mm, dtype=np.float64)
    by_total_T = np.zeros_like(y_mm, dtype=np.float64)

    valid_mask = np.ones_like(x_mm, dtype=np.bool_)

    for magnet in magnets:
        if not magnet.enabled:
            continue

        definition = magnet_catalog[magnet.definition_id]
        moment_Am2 = definition.moment_Am2

        dx_mm = x_mm - magnet.x_mm
        dy_mm = y_mm - magnet.y_mm

        distance_mm = np.hypot(dx_mm, dy_mm)

        # Точная граница радиуса допустима.
        inside = distance_mm < singularity_radius_mm
        valid_mask[inside] = False

        # мм -> м; исключаем сингулярности до деления на r.
        dx_m = dx_mm[valid_mask] / 1000.0
        dy_m = dy_mm[valid_mask] / 1000.0

        bx_T, by_T = dipole_field_si(dx_m, dy_m, moment_Am2, magnet.angle_deg)

        bx_total_T[valid_mask] += bx_T
        by_total_T[valid_mask] += by_T

    # Тл -> мТл.
    bx_mT = bx_total_T * 1000.0
    by_mT = by_total_T * 1000.0

    bx_mT[~valid_mask] = np.nan
    by_mT[~valid_mask] = np.nan
    return bx_mT, by_mT, valid_mask


def direction_from_components(bx_mT: float, by_mT: float) -> float | None:
    """Направление ненулевого вектора в градусах [0, 360)."""
    if bx_mT == 0.0 and by_mT == 0.0:
        return None
    direction = math.degrees(math.atan2(by_mT, bx_mT)) % 360.0
    # При малом отрицательном угле округление может дать ровно 360.
    return 0.0 if direction == 360.0 else direction


def compute_field_at(
    magnets: list[MagnetState],
    magnet_catalog: dict[str, MagnetDefinition],
    x_mm: float,
    y_mm: float,
    *,
    singularity_radius_mm: float,
    zero_field_epsilon_mT: float,
) -> FieldPoint:
    """Поле в одной точке: координаты в мм, компоненты и модуль в мТл."""
    x = finite_real(x_mm, "x_mm")
    y = finite_real(y_mm, "y_mm")
    radius = positive_real(singularity_radius_mm, "singularity_radius_mm")
    epsilon = positive_real(zero_field_epsilon_mT, "zero_field_epsilon_mT")
    bx, by, valid = field_components_at_points(
        magnets, magnet_catalog, np.array([x]), np.array([y]),
        singularity_radius_mm=radius,
    )
    if not valid[0]:
        return FieldPoint(math.nan, math.nan, math.nan, None, FieldStatus.INSIDE_SINGULARITY)

    bx_mT, by_mT = float(bx[0]), float(by[0])
    modB_mT = math.hypot(bx_mT, by_mT)
    if modB_mT < epsilon:
        return FieldPoint(bx_mT, by_mT, modB_mT, None, FieldStatus.ZERO_FIELD)
    direction = direction_from_components(bx_mT, by_mT)
    return FieldPoint(bx_mT, by_mT, modB_mT, direction, FieldStatus.OK)


def compute_field_grid(
    magnets: list[MagnetState],
    magnet_catalog: dict[str, MagnetDefinition],
    *,
    xmin_mm: float,
    xmax_mm: float,
    ymin_mm: float,
    ymax_mm: float,
    nx: int,
    ny: int,
    scene_revision: int,
    singularity_radius_mm: float,
) -> FieldGrid:
    """Оси включают границы; поля и маска имеют форму (ny, nx)."""
    xmin = finite_real(xmin_mm, "xmin_mm")
    xmax = finite_real(xmax_mm, "xmax_mm")
    ymin = finite_real(ymin_mm, "ymin_mm")
    ymax = finite_real(ymax_mm, "ymax_mm")
    nx = sample_count(nx, "nx")
    ny = sample_count(ny, "ny")
    radius = positive_real(singularity_radius_mm, "singularity_radius_mm")
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("grid minima must be less than maxima")

    x = np.linspace(xmin, xmax, nx)
    y = np.linspace(ymin, ymax, ny)
    xx, yy = np.meshgrid(x, y, indexing="xy")
    bx, by, valid = field_components_at_points(
        magnets, magnet_catalog, xx, yy, singularity_radius_mm=radius,
    )
    return FieldGrid(
        x_mm=x, y_mm=y, bx_mT=bx, by_mT=by, modB_mT=np.hypot(bx, by),
        valid_mask=valid, scene_revision=scene_revision,
    )
