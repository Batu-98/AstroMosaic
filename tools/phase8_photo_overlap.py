"""Measure two-panel sky alignment and optionally verify a Preserve Tone overlap."""

from __future__ import annotations

import argparse
import json
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import file_digest
from pathlib import Path

import numpy as np
from astropy.coordinates import ICRS
from numpy.typing import NDArray
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

from astromosaic.astrometry.solve import load_solution, read_solution_quality
from astromosaic.astrometry.solve_validation import outer_stars
from astromosaic.astrometry.stars import Star, StarField, measure_stars
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry, TileSky, read_panel_geometry
from astromosaic.io import PanelSource, open_panel
from astromosaic.pipeline.mosaic import PreviewFrame
from astromosaic.pipeline.srgb import SrgbTileSource
from astromosaic.resampling import sample, source_window
from astromosaic.storage.project import (
    load_project,
    open_project_sky_panel,
    preview_project,
    project_sky_bands,
)

type Pixels = NDArray[np.float64]
type Mask = NDArray[np.bool_]
type Indices = NDArray[np.intp]

_LUMA = np.array([0.2126, 0.7152, 0.0722])
_FULL_SCALE = 65_535
_MATCH_RADIUS = 5.0
_ALIGNMENT_TARGET = 0.5
_ALIGNMENT_MODELS = ("saved_wcs", "translation", "similarity")
_BLOCKS_PER_AXIS = 3
_MIN_BLOCK_TRAINING = 12
_MIN_REPORTED_BLOCK = 5
_MIN_OUTER_MATCHES = 10


@dataclass(frozen=True, slots=True)
class Panel:
    source: PanelSource
    geometry: PanelGeometry
    weight: float
    field: StarField
    saturation: float | None

    @property
    def size(self) -> tuple[int, int]:
        return self.source.descriptor.width, self.source.descriptor.height


@dataclass(frozen=True, slots=True)
class Samples:
    xy: Pixels
    rgb: Pixels
    covered: Mask
    quiet: Mask


@dataclass(frozen=True, slots=True)
class MatchedStars:
    candidates: int
    left_source: Pixels
    right_source: Pixels
    left_output: Pixels
    right_output: Pixels


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def _inside(xy: Pixels, size: tuple[int, int]) -> Mask:
    return ((xy >= -0.5) & (xy < np.asarray(size) - 0.5)).all(axis=1)


def star_positions(field: StarField) -> Pixels:
    return np.array([(star.x, star.y) for star in field.stars], dtype=np.float64).reshape(-1, 2)


def _read_rgb(
    source: PanelSource, xy: Pixels, usable: Mask, budget: int, *, reject_clipped: bool = False
) -> tuple[Pixels, Mask]:
    rgb = np.full((len(xy), 3), np.nan)
    clipped = np.zeros(len(xy), dtype=bool)
    descriptor = source.descriptor

    def read_batch(indices: Indices) -> None:
        points = xy[indices]
        x, y = points.T
        window = source_window(
            x, y, np.ones(len(indices), dtype=bool), descriptor.width, descriptor.height
        )
        if window is None:
            return
        area = window.region.width * window.region.height
        if source.tile_bytes(window.region) + 4 * area + 512 * len(indices) > budget:
            if len(indices) < 2:
                raise ValueError("The working budget cannot fit a diagnostic sample window.")
            axis = int(np.argmax(np.ptp(points, axis=0)))
            ordered = indices[np.argsort(points[:, axis])]
            middle = len(indices) // 2
            read_batch(ordered[:middle])
            read_batch(ordered[middle:])
            return

        tile = source.read_tile(window.region)
        if reject_clipped:
            full_scale = (tile.pixels >= 1).any(axis=-1)
            weight = map_coordinates(
                full_scale, window.coordinates, order=1, output=np.float64, prefilter=False
            )
            clipped[indices[window.indices]] = weight > 0
        selected, values = sample(tile, window)
        rgb[indices[selected]] = values

    read_batch(np.flatnonzero(usable))
    return rgb, clipped


def _sample_sky(panel: Panel, sky: TileSky, budget: int) -> Samples:
    x, y, usable = sky.in_panel(panel.geometry)
    xy = np.column_stack((x, y))
    rgb, clipped = _read_rgb(panel.source, xy, usable, budget, reject_clipped=True)
    covered = np.isfinite(rgb).all(axis=1)
    quiet = covered & ~clipped
    exclusions = panel.field.exclusions
    if exclusions.size:
        indices = np.flatnonzero(quiet)
        tree = cKDTree(exclusions[:, :2])
        radii = exclusions[:, 2] + 1
        neighbors = tree.query_ball_point(xy[indices], radii.max())
        for index, nearby in zip(indices, neighbors, strict=True):
            quiet[index] = not np.any(
                np.linalg.norm(xy[index] - exclusions[nearby, :2], axis=1) <= radii[nearby]
            )
    return Samples(xy, rgb, covered, quiet)


def _valid_aperture(panel: Panel, star: Star) -> bool:
    radius = float(np.clip(4 * star.fwhm / 2.355, 6, 17))
    halo = int(np.ceil(radius))
    x, y = round(star.x), round(star.y)
    tile = panel.source.read_tile(Region(x, y, 1, 1), halo=halo)
    region = tile.region
    xx = np.arange(region.x, region.x + region.width)
    yy = np.arange(region.y, region.y + region.height)
    aperture = (xx - star.x) ** 2 + (yy[:, None] - star.y) ** 2 <= radius**2
    return bool(
        tile.valid[aperture].all()
        and (panel.saturation is None or (tile.pixels[aperture] < panel.saturation).all())
    )


def _residuals(delta: Pixels) -> dict[str, float]:
    separation = np.linalg.norm(delta, axis=1)
    return {
        "median_px": float(np.median(separation)),
        "rms_px": float(np.sqrt(np.mean(separation**2))),
        "p95_px": float(np.percentile(separation, 95)),
    }


def _comparison(selection: Mask, residuals: Pixels, *, minimum_support: int) -> dict[str, object]:
    count = int(selection.sum())
    comparable = selection & np.isfinite(residuals).all(axis=(1, 2))
    tested = int(comparable.sum())
    statistics = {
        name: _residuals(residuals[comparable, index]) if tested >= minimum_support else None
        for index, name in enumerate(_ALIGNMENT_MODELS)
    }
    return {"matches": count, "compared_matches": tested, **statistics}


def overlap_blocks(left: Pixels) -> tuple[Pixels, Pixels, Indices | None]:
    """Assign fixed output positions to the same nine regions in every comparison."""
    low, high = left.min(axis=0), left.max(axis=0)
    span = high - low
    if np.any(span == 0):
        return low, high, None
    normalized = (left - low) / span
    column, row = np.clip(
        (_BLOCKS_PER_AXIS * normalized).astype(np.intp), 0, _BLOCKS_PER_AXIS - 1
    ).T
    return low, high, row * _BLOCKS_PER_AXIS + column


def _spatial_alignment(left: Pixels, right: Pixels, outer: Mask) -> dict[str, object]:
    low, high, block = overlap_blocks(left)
    if block is None:
        return {"status": "no two-dimensional support"}
    displacement = left - right
    residuals = np.full((len(left), len(_ALIGNMENT_MODELS), 2), np.nan)
    residuals[:, 0] = displacement

    # A whole block is absent from each fit. Pair assignments are fixed across all models.
    blocks = []
    for cell in range(_BLOCKS_PER_AXIS**2):
        held = block == cell
        training = ~held
        if held.any() and training.sum() >= _MIN_BLOCK_TRAINING:
            center = right[training].mean(axis=0)
            centered = right[training] - center
            singular = np.linalg.svd(centered, compute_uv=False)
            if singular[0] > 0 and singular[1] >= 0.05 * singular[0]:
                delta = displacement[training]
                residuals[held, 1] = displacement[held] - np.median(delta, axis=0)
                x, y = centered.T
                u, v = (delta - delta.mean(axis=0)).T
                norm = np.sum(x * x + y * y)
                scale_delta = (x @ u + y @ v) / norm
                rotation_term = (x @ v - y @ u) / norm
                transform = np.array([[scale_delta, rotation_term], [-rotation_term, scale_delta]])
                correction = delta.mean(axis=0) + (right[held] - center) @ transform
                residuals[held, 2] = displacement[held] - correction
        comparison = _comparison(held, residuals, minimum_support=_MIN_REPORTED_BLOCK)
        blocks.append(
            {
                "row": cell // _BLOCKS_PER_AXIS,
                "column": cell % _BLOCKS_PER_AXIS,
                "median_wcs_dx_dy_px": np.median(displacement[held], axis=0).tolist()
                if held.sum() >= _MIN_REPORTED_BLOCK
                else None,
                **comparison,
            }
        )

    aggregate = _comparison(np.ones(len(left), dtype=bool), residuals, minimum_support=8)
    edge = _comparison(outer, residuals, minimum_support=_MIN_OUTER_MATCHES)
    complete = aggregate["matches"] == aggregate["compared_matches"]
    return {
        "status": "complete" if complete else "incomplete training support",
        "left_output_bounds_px": [low.tolist(), high.tolist()],
        "all": aggregate,
        "outer_either_detector": edge,
        "blocks": blocks,
    }


def match_stars(
    left: Panel, right: Panel, target: PanelGeometry, size: tuple[int, int]
) -> MatchedStars:
    left_source, right_source = (star_positions(panel.field) for panel in (left, right))
    a = target.inverse(left.geometry.forward(*left_source.T))
    b = target.inverse(right.geometry.forward(*right_source.T))
    left_index = np.flatnonzero(_inside(a, size))
    right_index = np.flatnonzero(_inside(b, size))
    if min(len(left_index), len(right_index)) < 2:
        raise ValueError("The output grid does not contain enough measured stars in both panels.")
    a, b = a[left_index], b[right_index]
    distance, neighbors = cKDTree(b).query(a, k=2, distance_upper_bound=_MATCH_RADIUS)
    _, reverse = cKDTree(a).query(b, distance_upper_bound=_MATCH_RADIUS)
    i = np.flatnonzero(np.isfinite(distance[:, 0]) & (distance[:, 0] <= 0.8 * distance[:, 1]))
    i = i[reverse[neighbors[i, 0]] == i]
    j = neighbors[i, 0]
    keep = np.array(
        [
            _valid_aperture(left, left.field.stars[left_index[k]])
            and _valid_aperture(right, right.field.stars[right_index[m]])
            for k, m in zip(i, j, strict=True)
        ],
        dtype=bool,
    )
    if keep.sum() < 8:
        raise ValueError("The overlap does not contain eight matched, unclipped stars.")
    return MatchedStars(
        len(i),
        left_source[left_index[i[keep]]],
        right_source[right_index[j[keep]]],
        a[i[keep]],
        b[j[keep]],
    )


def _stellar_alignment(
    left: Panel, right: Panel, target: PanelGeometry, size: tuple[int, int]
) -> dict[str, object]:
    matches = match_stars(left, right, target, size)
    matched_left, matched_right = matches.left_output, matches.right_output
    delta = matched_left - matched_right
    holdout = np.lexsort((matched_left[:, 1], matched_left[:, 0]))[::4]
    training = np.ones(len(delta), dtype=bool)
    training[holdout] = False
    shift = np.median(delta[training], axis=0)
    raw = _residuals(delta[holdout])
    translated = _residuals(delta[holdout] - shift)
    outer = outer_stars(matches.left_source, left.size) | outer_stars(
        matches.right_source, right.size
    )
    return {
        "candidates": matches.candidates,
        "unclipped_matches": len(delta),
        "held_out_matches": len(holdout),
        "all": _residuals(delta),
        "held_out": raw,
        "meets_geometry_target": raw["p95_px"] < _ALIGNMENT_TARGET,
        "right_to_left_translation_px": shift.tolist(),
        "held_out_with_translation": translated,
        "translation_meets_geometry_target": translated["p95_px"] < _ALIGNMENT_TARGET,
        "spatial_holdout": _spatial_alignment(matched_left, matched_right, outer),
    }


def _background(
    panels: tuple[Panel, Panel],
    left: Samples,
    right: Samples,
    sky: TileSky,
    row_width: int,
    step: int,
) -> dict[str, object]:
    common = left.covered & right.covered
    quiet = left.quiet & right.quiet
    if np.count_nonzero(quiet) < 32:
        raise ValueError("The overlap has fewer than 32 jointly masked background samples.")
    a, b = left.rgb[quiet], right.rgb[quiet]
    difference = (a - b) @ _LUMA
    width = step * common.reshape(-1, row_width).sum(axis=1)
    covariates = {
        "output_x": sky.x[quiet],
        "output_y": sky.y[quiet],
        "shared_row_width": np.repeat(width, row_width)[quiet],
    }
    for name, panel, samples in zip(("left", "right"), panels, (left, right), strict=True):
        center = (np.asarray(panel.size) - 1) / 2
        covariates[f"{name}_detector_radius"] = np.linalg.norm(samples.xy[quiet] - center, axis=1)
    return {
        "paired_coverage_samples": int(common.sum()),
        "paired_background_samples": int(quiet.sum()),
        "left_median_linear_y": float(np.median(a @ _LUMA)),
        "right_median_linear_y": float(np.median(b @ _LUMA)),
        "left_minus_right_median_linear_rgb": np.median(a - b, axis=0).tolist(),
        "left_minus_right_median_linear_y": float(np.median(difference)),
        "median_absolute_difference_linear_y": float(np.median(np.abs(difference))),
        "p95_absolute_difference_linear_y": float(np.percentile(np.abs(difference), 95)),
        "spearman": {
            name: float(spearmanr(values, difference).statistic)
            if np.ptp(values) and np.ptp(difference)
            else None
            for name, values in covariates.items()
        },
    }


def _compare_export(
    photo: PanelSource, xy: Pixels, left: Samples, right: Samples, weights: Pixels, budget: int
) -> dict[str, int]:
    rgb, _ = _read_rgb(photo, xy, np.ones(len(xy), dtype=bool), budget)
    covered = left.covered | right.covered
    if not np.array_equal(np.isfinite(rgb).all(axis=1), covered):
        raise ValueError("Sampled photo coverage disagrees with the source panels.")
    if not covered.any():
        raise ValueError("The diagnostic lattice has no covered output pixels.")
    common = left.covered & right.covered
    expected = np.where(left.covered[:, None], left.rgb, right.rgb)
    expected[common] = weights[0] * left.rgb[common] + weights[1] * right.rgb[common]
    expected = expected[covered]
    encoded = np.where(
        expected <= 0.0031308, 12.92 * expected, 1.055 * expected ** (1 / 2.4) - 0.055
    )
    error = int(np.abs(rgb[covered] - np.rint(_FULL_SCALE * encoded)).max())
    if error > 2:
        raise ValueError(f"The Preserve Tone reference differs by up to {error} codes.")
    return {"sampled_pixels": len(xy), "covered_pixels": int(covered.sum()), "max_rgb_error": error}


def _edge_steps(
    entering: Panel,
    continuing: Panel,
    fraction: float,
    target: PanelGeometry,
    size: tuple[int, int],
    budget: int,
) -> dict[str, dict[str, int | float | None]]:
    # Each strip uses four output samples on each side of the projected detector edge.
    offsets = np.array([-8, -6, -4, -2, 2, 4, 6, 8], dtype=np.float64)
    report = {}
    for axis, names in enumerate((("left", "right"), ("top", "bottom"))):
        length = entering.size[1 - axis]
        along = np.linspace(0, length - 1, 96)
        for side, name in enumerate(names):
            points = np.empty((len(along), len(offsets), 2))
            points[:, :, 1 - axis] = along[:, None]
            boundary = entering.size[axis] - 0.5 if side else -0.5
            points[:, :, axis] = boundary + (-offsets if side else offsets)
            x, y = points.reshape(-1, 2).T
            xy = np.rint(target.inverse(entering.geometry.forward(x, y)))
            shape = (len(along), len(offsets))
            raster = xy.reshape(*shape, 2)
            distinct = np.ones(shape, dtype=bool)
            distinct[:, 1:] = np.any(raster[:, 1:] != raster[:, :-1], axis=2)
            usable = _inside(xy, size) & distinct.ravel()
            sky = TileSky.from_pixels(target, *xy.T)
            a, b = (_sample_sky(panel, sky, budget) for panel in (entering, continuing))
            inside = (usable & a.quiet & b.quiet).reshape(shape)[:, 4:]
            outside = (usable & ~a.covered & b.quiet).reshape(shape)[:, :4]
            enough = (inside.sum(axis=1) >= 3) & (outside.sum(axis=1) >= 3)
            difference = ((a.rgb - b.rgb) @ _LUMA).reshape(shape)[enough, 4:]
            step = fraction * np.nanmedian(np.where(inside[enough], difference, np.nan), axis=1)
            report[name] = {
                "strips": int(enough.sum()),
                "median_added_step_linear_y": float(np.median(step)) if step.size else None,
                "p95_absolute_step_linear_y": float(np.percentile(np.abs(step), 95))
                if step.size
                else None,
            }
    return report


def _photo_geometry(photo: PanelSource, preview: PreviewFrame) -> PanelGeometry:
    header = photo.header
    if (header.get("AMINTENT"), header.get("PHOTOTON")) != ("PHOTO", "preserve"):
        raise ValueError("Use an AstroMosaic Preserve Tone photo TIFF.")
    size = (photo.descriptor.width, photo.descriptor.height)
    if size != preview.output_size:
        raise ValueError("The photo dimensions do not match the project's resolved grid.")
    target = read_panel_geometry(header, *size)
    x, y = np.meshgrid(*(np.linspace(0, length - 1, 3) for length in size))
    assert preview.output_wcs is not None
    expected_sky = preview.output_wcs.pixel_to_world(x.ravel(), y.ravel())
    photo_sky = target.forward(x.ravel(), y.ravel())
    valid = np.isfinite(expected_sky.spherical.lat.deg)
    separation = photo_sky[valid].separation(expected_sky[valid]).deg
    if (
        not np.array_equal(np.isfinite(photo_sky.spherical.lat.deg), valid)
        or not valid.any()
        or not np.allclose(separation, 0, atol=1e-9)
    ):
        raise ValueError("The photo WCS does not match the project's resolved grid.")
    return target


def _photo_overlap(
    photo: PanelSource,
    left: Panel,
    right: Panel,
    target: PanelGeometry,
    size: tuple[int, int],
    budget: int,
) -> dict[str, object]:
    weights = np.array([left.weight, right.weight])
    weights /= weights.max()
    weights /= weights.sum()
    step = max(96, (max(size) + 127) // 128)
    axes = [np.arange(min(step // 2, (length - 1) // 2), length, step) for length in size]
    grid_x, grid_y = np.meshgrid(*axes)
    xy = np.column_stack((grid_x.ravel(), grid_y.ravel())).astype(np.float64)
    sky = TileSky.from_pixels(target, *xy.T)
    a, b = (_sample_sky(panel, sky, budget) for panel in (left, right))
    return {
        "lattice_spacing_px": step,
        "preserve_tone_reference": _compare_export(photo, xy, a, b, weights, budget),
        "background": _background((left, right), a, b, sky, grid_x.shape[1], step),
        "edge_steps_in_panel_order": [
            _edge_steps(left, right, float(weights[0]), target, size, budget),
            _edge_steps(right, left, float(weights[1]), target, size, budget),
        ],
    }


def measure(project_path: Path, photo_path: Path | None = None) -> dict[str, object]:
    project = load_project(project_path)
    context = JobContext()
    budget = project.render.max_working_bytes
    bands = project_sky_bands(project, context)
    indices = project.sky_indices()
    if len(bands) != 1 or len(indices) != 2 or project.refinement is not None:
        raise ValueError("Use a two-panel sky project with one band and relative refinement off.")
    records = [project.panels[index] for index in indices]
    fingerprints = {
        path: _sha256(path)
        for path in (
            project_path,
            *(reference.path for record in records for _, reference in record.references()),
        )
    }
    preview = preview_project(project, context, allow_visual=True)
    if preview.output_wcs is None:
        raise ValueError("The selected panels require a resolved sky grid.")
    if photo_path is not None and not preview.visual_only:
        raise ValueError("The selected panels must support the sRGB photo workflow.")
    size = preview.output_size
    scale = (preview.fitted_grid or project.render).scale_arcsec
    target = PanelGeometry(preview.output_wcs, ICRS())
    with ExitStack() as opened:
        photo = None
        if photo_path is not None:
            photo = opened.enter_context(open_panel(photo_path, max_tile_bytes=budget))
            target = _photo_geometry(photo, preview)
        del preview

        panels = []
        sources = []
        for record in records:
            source = opened.enter_context(open_project_sky_panel(record, budget, context))
            quality = {}
            if record.wcs_sidecar is not None:
                sidecar = record.wcs_sidecar.path
                geometry, provenance = load_solution(sidecar, source)
                quality = read_solution_quality(sidecar)
            else:
                geometry = read_panel_geometry(
                    source.header, source.descriptor.width, source.descriptor.height
                )
                provenance = "embedded WCS"
            srgb = source.descriptor.icc_encoding == "srgb"
            linear: PanelSource = SrgbTileSource(source, budget) if srgb else source
            declared = source.header.get("SATURATE")
            saturation = float(declared) if declared is not None else None
            if srgb:
                saturation = 1.0
            panels.append(
                Panel(
                    linear,
                    geometry,
                    record.weight,
                    measure_stars(linear, budget, context),
                    saturation,
                )
            )
            sources.append(
                {
                    "name": record.source.path.name,
                    "sha256": fingerprints[record.source.path],
                    "wcs_sidecar_sha256": fingerprints[record.wcs_sidecar.path]
                    if record.wcs_sidecar is not None
                    else None,
                    "wcs_provenance": provenance,
                    "catalog_quality": {
                        field: quality[field]
                        for field in (
                            "grade",
                            "model",
                            "rms_arcsec",
                            "held_out_p95_source_px",
                            "held_out_outer_p95_source_px",
                        )
                        if field in quality
                    },
                    "aperture_saturation_threshold": saturation,
                }
            )
        left, right = panels
        report = {
            "sources": sources,
            "project_sha256": fingerprints[project_path],
            "size": size,
            "output_scale_arcsec": scale,
            "working_budget_bytes": budget,
            "alignment": _stellar_alignment(left, right, target, size),
        }
        if photo is not None and photo_path is not None:
            report.update(_photo_overlap(photo, left, right, target, size, budget))
            report["photo_sha256"] = _sha256(photo_path)
    if any(_sha256(path) != digest for path, digest in fingerprints.items()):
        raise ValueError("A source, sidecar, or project changed during the overlap measurement.")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Saved project for the solved sky pair")
    parser.add_argument("photo", nargs="?", type=Path, help="Full-resolution Preserve Tone export")
    arguments = parser.parse_args()
    try:
        report = measure(arguments.project, arguments.photo)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
