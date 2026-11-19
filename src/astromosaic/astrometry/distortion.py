"""Fit supported TAN/SIP models and diagnose the original detector domain."""

from dataclasses import dataclass
from math import ceil, comb

import numpy as np
from astropy.coordinates import SkyCoord
from astropy.wcs import WCS, Sip
from numpy.typing import NDArray

from astromosaic.astrometry.solve_validation import (
    MIN_MATCHES,
    MODEL_GRID,
    Associations,
    FloatArray,
    QualityRejected,
    cells,
    outer_stars,
    p95,
    regional_metrics,
    require_quality,
    residuals,
    rms,
)
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.geometry import (
    ROUND_TRIP_TOLERANCE,
    PanelGeometry,
    read_panel_geometry,
    tan_output_wcs,
)

_TRAIN_MIN = {2: 30, 3: 70}
_OUTER_MIN = 10


def _terms(order: int) -> list[tuple[int, int]]:
    return [(0, 0), (1, 0), (0, 1)] + [
        (i, degree - i) for degree in range(2, order + 1) for i in range(degree + 1)
    ]


def _translate(
    terms: list[tuple[int, int]], coefficients: FloatArray, origin: FloatArray
) -> FloatArray:
    """Expand a polynomial about the new tangent-point pixel."""
    u, v = origin
    return np.stack(
        [
            sum(
                (
                    c * comb(p, i) * comb(q, j) * u ** (p - i) * v ** (q - j)
                    for (p, q), c in zip(terms, coefficients, strict=True)
                    if p >= i and q >= j
                ),
                np.zeros(2),
            )
            for i, j in terms
        ]
    )


def _fit(
    xy: FloatArray,
    tangent: FloatArray,
    anchor: tuple[float, float],
    size: tuple[int, int],
    order: int,
    context: JobContext,
) -> PanelGeometry:
    context.check_cancelled()
    width, height = size
    center = (np.array(size, dtype=np.float64) - 1) / 2
    norm = max(size) / 2
    x, y = ((xy - center) / norm).T
    terms = _terms(order)
    design = np.column_stack([x**i * y**j for i, j in terms])
    fit, _, rank, _ = np.linalg.lstsq(design, tangent, rcond=1e-10)
    if rank != len(terms) or not np.all(np.isfinite(fit)):
        raise QualityRejected("The catalog stars do not constrain the requested distortion model.")
    root = np.zeros(2, dtype=np.float64)
    try:
        for _ in range(10):
            shifted = _translate(terms, fit, root)
            step = np.linalg.solve(shifted[1:3].T, shifted[0])
            if np.linalg.norm(step) * norm <= 1e-7:
                break
            root -= step
            if not np.all(np.isfinite(root)) or np.linalg.norm(root) > 4:
                raise QualityRejected("The fitted tangent point is outside the supported domain.")
        else:
            raise QualityRejected("The fitted tangent point did not converge.")
        linear = shifted[1:3].T
        inverse_linear = np.linalg.inv(linear)
    except np.linalg.LinAlgError as error:
        raise QualityRejected("The catalog star fit has a singular pixel transform.") from error

    wcs = WCS(naxis=2)
    wcs.wcs.radesys = "ICRS"
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = anchor
    wcs.wcs.crpix = center + root * norm + 1
    wcs.wcs.cd = linear / norm
    if order:
        a, b = np.zeros((order + 1, order + 1)), np.zeros((order + 1, order + 1))
        for (i, j), term in zip(terms[3:], shifted[3:], strict=True):
            a[i, j], b[i, j] = inverse_linear @ term / norm ** (i + j - 1)
        wcs.wcs.ctype = ["RA---TAN-SIP", "DEC--TAN-SIP"]
        wcs.sip = Sip(a, b, None, None, wcs.wcs.crpix)
    context.check_cancelled()
    return read_panel_geometry(wcs.to_header(relax=True), width, height)


def _jacobian(geometry: PanelGeometry, xy: FloatArray) -> FloatArray:
    sky = geometry.forward(*xy.T)
    axes = []
    for step in ((0.5, 0), (0, 0.5)):
        ahead = sky.spherical_offsets_to(geometry.forward(*(xy + step).T))
        behind = sky.spherical_offsets_to(geometry.forward(*(xy - step).T))
        axes.append(np.column_stack([(a - b).arcsec for a, b in zip(ahead, behind, strict=True)]))
    return np.stack(axes, axis=-1)


def _skew(jacobian: FloatArray) -> FloatArray:
    lengths = np.linalg.norm(jacobian, axis=-2)
    cos_angle = np.sum(jacobian[..., 0] * jacobian[..., 1], axis=-1) / np.prod(lengths, axis=-1)
    return np.degrees(np.arccos(np.clip(cos_angle, -1, 1))) - 90.0


def _linear_only(geometry: PanelGeometry) -> PanelGeometry:
    wcs = geometry.wcs.deepcopy()
    wcs.sip = None
    wcs.wcs.ctype = [axis.removesuffix("-SIP") for axis in wcs.wcs.ctype]
    return PanelGeometry(wcs, geometry.frame)


def field_geometry(
    geometry: PanelGeometry,
    size: tuple[int, int],
    context: JobContext,
    *,
    parity: int | None = None,
) -> dict[str, object]:
    """Measure local scales and shear, and reject inverse failures and folds."""
    context.check_cancelled()
    width, height = size
    xx, yy = np.meshgrid(
        np.linspace(-0.5, width - 0.5, MODEL_GRID), np.linspace(-0.5, height - 0.5, MODEL_GRID)
    )
    grid = np.column_stack((xx.ravel(), yy.ravel()))
    sky = geometry.forward(*grid.T)
    error = np.linalg.norm(geometry.inverse(sky) - grid, axis=1)
    if not np.all(np.isfinite(error)) or np.max(error) > ROUND_TRIP_TOLERANCE:
        raise QualityRejected("The solved WCS fails the original-domain inverse grid check.")
    jac = _jacobian(geometry, grid)
    det = np.linalg.det(jac)
    scales = np.linalg.norm(jac, axis=1)
    mid = len(grid) // 2
    sign = int(np.sign(det[mid])) if np.isfinite(det[mid]) else 0
    if (
        not np.all(np.isfinite(jac))
        or not sign
        or (parity is not None and sign != parity)
        or np.any(det * sign <= 1e-8 * np.prod(scales, axis=1))
    ):
        raise QualityRejected("The candidate changes parity or folds in the original pixel domain.")
    base = _linear_only(geometry)
    linear = np.asarray(base.wcs.pixel_scale_matrix, dtype=np.float64) * 3600
    base_sky = base.forward(*grid.T)
    angular_displacement = np.asarray(sky.separation(base_sky).arcsec)
    displacement = base.inverse(sky) - grid if geometry.wcs.sip is not None else np.zeros_like(grid)
    pixel_displacement = np.linalg.norm(displacement, axis=1)
    if not np.all(np.isfinite(angular_displacement)) or not np.all(np.isfinite(pixel_displacement)):
        raise QualityRejected("The distortion comparison to the linear projection is nonfinite.")
    local_skew = _skew(jac)
    return {
        "parity": sign,
        "center_scale_arcsec_px": scales[mid].tolist(),
        "linear_skew_deg": float(_skew(linear)),
        "linear_rotation_deg_from_east": float(np.degrees(np.arctan2(linear[1, 0], linear[0, 0]))),
        "linear_scale_arcsec_px": np.linalg.norm(linear, axis=0).tolist(),
        "maximum_inverse_error_source_px": float(error.max()),
        "maximum_model_displacement_source_px": float(pixel_displacement.max()),
        "model_grid": [
            {
                "x": float(x),
                "y": float(y),
                "model_displacement_source_px": float(pixel_displacement[i]),
                "model_vector_source_px": displacement[i].tolist(),
                "model_displacement_arcsec": float(angular_displacement[i]),
                "local_scale_arcsec_px": scales[i].tolist(),
                "local_anisotropy": float(max(scales[i]) / min(scales[i])),
                "local_area_scale_arcsec2_px2": float(abs(det[i])),
                "local_skew_deg": float(local_skew[i]),
            }
            for i, (x, y) in enumerate(grid)
        ],
    }


def _spatial_split(
    xy: FloatArray,
    size: tuple[int, int],
) -> tuple[NDArray[np.intp], NDArray[np.intp]]:
    count = len(xy)
    empty = np.empty(0, dtype=np.intp)
    all_indexes = np.arange(count, dtype=np.intp)
    n_hold = max(10, ceil(0.2 * count))
    if count - n_hold < MIN_MATCHES:
        return all_indexes, empty
    outer = outer_stars(xy, size)
    cell = cells(xy, size, 3)
    shuffled = np.random.default_rng(360601).permutation(count)
    chosen: set[int] = set()
    for limit, pool in ((_OUTER_MIN, shuffled[outer[shuffled]]), (n_hold, shuffled)):
        groups = [iter(pool[cell[pool] == index]) for index in range(9)]
        while len(chosen) < limit:
            before = len(chosen)
            for group in groups:
                index = next((int(i) for i in group if i not in chosen), None)
                if index is not None:
                    chosen.add(index)
                if len(chosen) == limit:
                    break
            if len(chosen) == before:
                break
    held_out = np.array(sorted(chosen), dtype=np.intp)
    training = np.setdiff1d(all_indexes, held_out, assume_unique=True)
    return training, held_out


@dataclass(frozen=True, slots=True)
class ModelCheck:
    geometry: PanelGeometry
    order: int
    field: dict[str, object]
    angular: FloatArray
    pixels: FloatArray
    hold_p95: float | None
    outer_p95: float | None
    rms_limit: float


def validate_models(
    seed: PanelGeometry,
    size: tuple[int, int],
    pairs: Associations,
    context: JobContext,
    *,
    strict_edges: bool = False,
) -> tuple[PanelGeometry, dict[str, object]]:
    """Accept the simplest supported model that passes catalog and domain checks."""
    xy = pairs.xy
    training, held = _spatial_split(xy, size)
    outer = outer_stars(xy, size)
    outer_held = held[outer[held]]
    outer_sectors = len(np.unique(cells(xy[outer_held], size, 3)))
    outer_support = len(outer_held) >= _OUTER_MIN and outer_sectors >= 3
    spatial_support = (
        len(np.unique(cells(xy[training], size, 3))) >= 6
        and len(np.unique(cells(xy[training], size, 2))) == 4
        and outer_support
    )

    # Keep the localized sky tangent point for every degree. Fit in ICRS
    # tangent coordinates with a normalized detector basis, including at RA wrap.
    seed_wcs = seed.wcs.wcs
    anchor_sky = SkyCoord(
        seed_wcs.crval[seed_wcs.lng], seed_wcs.crval[seed_wcs.lat], unit="deg", frame=seed.frame
    ).icrs
    anchor = float(anchor_sky.ra.deg), float(anchor_sky.dec.deg)
    projection = tan_output_wcs(anchor, (1, 1), 3600, 0, Region(0, 0, 1, 1))
    tangent = projection.wcs_world2pix(pairs.sky.ra.deg, pairs.sky.dec.deg, 0)
    target = np.column_stack(tangent) * (-1, 1)
    parity = int(np.sign(np.linalg.det(seed.wcs.pixel_scale_matrix)))

    def measure(candidate: PanelGeometry, order: int) -> ModelCheck:
        field = field_geometry(candidate, size, context, parity=parity)
        angular, pixels = residuals(candidate, xy, pairs.sky)
        local = _jacobian(candidate, np.array([(np.array(size) - 1) / 2], dtype=np.float64))
        sx, sy = np.linalg.norm(local, axis=1)[0]
        # An inaccurate TAN is still the baseline for a supported SIP comparison.
        limit = max(3.0, 2.0 * min(float(sx), float(sy)))
        return ModelCheck(
            candidate,
            order,
            field,
            angular,
            pixels,
            p95(pixels[held]) if len(held) else None,
            p95(pixels[outer_held]) if outer_support else None,
            limit,
        )

    selected = measure(_fit(xy[training], target[training], anchor, size, 0, context), 0)
    models: list[dict[str, object]] = [
        {
            "order": 0,
            "held_out_p95_source_px": selected.hold_p95,
            "held_out_outer_p95_source_px": selected.outer_p95,
        }
    ]
    for order, minimum in _TRAIN_MIN.items():
        context.check_cancelled()
        if len(training) < minimum or not spatial_support:
            models.append(
                {"order": order, "reason": "Insufficient spatial training or held-out support."}
            )
            continue
        try:
            evaluated = measure(
                _fit(xy[training], target[training], anchor, size, order, context), order
            )
        except (ValueError, OverflowError) as error:
            models.append({"order": order, "reason": str(error)})
            continue
        assert evaluated.hold_p95 is not None and selected.hold_p95 is not None
        assert evaluated.outer_p95 is not None and selected.outer_p95 is not None
        improves = evaluated.hold_p95 <= 0.9 * selected.hold_p95
        edge_allowance = max(0.05, 0.02 * selected.outer_p95)
        promotes = (
            improves
            and evaluated.outer_p95 <= selected.outer_p95 + edge_allowance
            and rms(evaluated.angular) <= evaluated.rms_limit
        )
        models.append(
            {
                "order": order,
                "promoted": promotes,
                "held_out_p95_source_px": evaluated.hold_p95,
                "held_out_outer_p95_source_px": evaluated.outer_p95,
            }
        )
        if promotes:
            selected = evaluated

    scales = selected.field["center_scale_arcsec_px"]
    assert isinstance(scales, list) and len(scales) == 2
    angular, pixels = selected.angular, selected.pixels
    angular_rms = rms(angular)
    limit = require_quality(len(xy), angular_rms, (scales[0], scales[1]))
    held_out_evidence = {
        "held_out_matches": len(held),
        "held_out_p95_source_px": selected.hold_p95,
        "held_out_outer_matches": len(outer_held),
        "held_out_outer_sectors": outer_sectors,
        "held_out_outer_p95_source_px": selected.outer_p95,
    }
    rejection_evidence = {
        **held_out_evidence,
        "unique_matches": len(xy),
        "rms_arcsec": angular_rms,
        "rms_limit_arcsec": limit,
    }
    edge_status = "insufficient"
    if selected.outer_p95 is not None and selected.hold_p95 is not None:
        edge_status = "supported-pass"
        if selected.outer_p95 > 1.5 or selected.hold_p95 > 1:
            raise QualityRejected(
                f"The held-out P95 is {selected.hold_p95:.3g} px overall and "
                f"{selected.outer_p95:.3g} px at the edges. The limits are 1 and 1.5 px.",
                {**rejection_evidence, "edge_status": "supported-fail"},
                gate="held-out",
            )
    if strict_edges and edge_status != "supported-pass":
        raise QualityRejected(
            "Too few catalog stars support strict field-edge validation.",
            {**rejection_evidence, "edge_status": edge_status},
            gate="edge-support",
        )
    context.check_cancelled()
    return selected.geometry, {
        "grade": "catalog-validated",
        "evidence": "Unique catalog pairs, with a spatial holdout from the application fits. Native fit membership is unavailable.",
        "model": "TAN" if not selected.order else f"SIP-{selected.order}",
        "unique_matches": len(xy),
        "chance_control_matches": pairs.chance_matches,
        "catalog_candidates": pairs.catalog_candidates,
        "rms_arcsec": angular_rms,
        "rms_limit_arcsec": limit,
        "p95_arcsec": p95(angular),
        "max_arcsec": float(angular.max()),
        "rms_source_px": rms(pixels),
        "p95_source_px": p95(pixels),
        "max_source_px": float(pixels.max()),
        "training_matches": len(training),
        **held_out_evidence,
        "edge_status": edge_status,
        "models": models,
        "field_geometry": selected.field,
        "measured_regions": regional_metrics(xy, size, angular, pixels, held),
    }
