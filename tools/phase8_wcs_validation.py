"""Compare TAN and SIP candidates with held-out Gaia stars and a fixed photo grid."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import numpy as np
from astropy.coordinates import ICRS, SkyCoord
from scipy.spatial import cKDTree

from astromosaic.astrometry.astap_catalog import CatalogStar
from astromosaic.astrometry.distortion import _fit, field_geometry
from astromosaic.astrometry.solve import load_solution, read_solution_diagnostics
from astromosaic.astrometry.solve_validation import (
    MIN_MATCHES,
    CatalogRegion,
    QualityRejected,
    associate,
    cells,
    outer_stars,
    residuals,
)
from astromosaic.astrometry.stars import measure_stars
from astromosaic.core import Region
from astromosaic.core.job import JobContext
from astromosaic.geometry import PanelGeometry, tan_output_wcs
from astromosaic.io import PanelSource
from astromosaic.pipeline.srgb import SrgbTileSource
from astromosaic.storage.project import (
    load_project,
    open_project_sky_panel,
    preview_project,
    project_sky_bands,
)
from tools.phase8_photo_overlap import (
    Indices,
    Mask,
    MatchedStars,
    Panel,
    Pixels,
    _sha256,
    _valid_aperture,
    match_stars,
    overlap_blocks,
    star_positions,
)

_MODELS = {"tan": 0, "sip2": 2, "sip3": 3}
_TRAINING_FLOORS = {0: MIN_MATCHES, 2: 30, 3: 70}
_EXCLUSION_PX = 5.0
_MIN_OUTER_MATCHES = 10
_OVERLAP_TARGET_PX = 0.5

type GaiaKey = tuple[float, float]


class Stats(TypedDict):
    matches: int
    median_px: float
    rms_px: float
    p95_px: float


@dataclass(frozen=True, slots=True)
class PanelSample:
    panel: Panel
    raw_centroids: Pixels
    xy: Pixels
    sky: SkyCoord
    keys: tuple[GaiaKey, ...]
    held_out: Mask
    chance_matches: int


@dataclass(frozen=True, slots=True)
class CatalogCheck:
    geometry: PanelGeometry
    overall: Stats
    outer: Stats
    p95_arcsec: float
    maximum_inverse_error_px: float


def _stats(errors: Pixels) -> Stats:
    return {
        "matches": len(errors),
        "median_px": float(np.median(errors)),
        "rms_px": float(np.sqrt(np.mean(errors**2))),
        "p95_px": float(np.percentile(errors, 95)),
    }


def _outside_centroids(xy: Pixels, reference: Pixels) -> Mask:
    return np.asarray(cKDTree(reference).query(xy)[0] > _EXCLUSION_PX, dtype=bool)


def _sample_panel(
    source: PanelSource,
    geometry: PanelGeometry,
    budget: int,
    query: Callable[[CatalogRegion], list[CatalogStar]],
    context: JobContext,
) -> PanelSample:
    if source.descriptor.icc_encoding != "srgb":
        raise ValueError("The WCS candidate comparison requires the original sRGB TIFFs.")
    raw = star_positions(measure_stars(source, budget, context))
    linear = SrgbTileSource(source, budget)
    panel = Panel(linear, geometry, 1.0, measure_stars(linear, budget, context), 1.0)
    linear_xy = star_positions(panel.field)
    associated = associate(geometry, panel.size, linear_xy, query, context)
    _, indices = cKDTree(linear_xy).query(associated.xy)
    keep = np.array(
        [_valid_aperture(panel, panel.field.stars[index]) for index in indices], dtype=bool
    )
    xy, sky = associated.xy[keep], associated.sky[keep]
    independent = _outside_centroids(xy, raw) & _outside_centroids(geometry.inverse(sky), raw)
    keys = tuple(zip(sky.ra.deg.tolist(), sky.dec.deg.tolist(), strict=True))
    return PanelSample(panel, raw, xy, sky, keys, independent, associated.chance_matches)


def _supported(xy: Pixels, size: tuple[int, int]) -> bool:
    outer = outer_stars(xy, size)
    return (
        len(xy) >= MIN_MATCHES
        and len(np.unique(cells(xy, size, 2))) == 4
        and len(np.unique(cells(xy, size, 3))) >= 6
        and int(np.count_nonzero(outer)) >= _MIN_OUTER_MATCHES
        and len(np.unique(cells(xy[outer], size, 2))) >= 3
    )


def _check_catalog(
    geometry: PanelGeometry, sample: PanelSample, parity: int, context: JobContext
) -> CatalogCheck:
    size = sample.panel.size
    inverse_error = field_geometry(geometry, size, context, parity=parity)[
        "maximum_inverse_error_source_px"
    ]
    assert isinstance(inverse_error, float)
    xy = sample.xy[sample.held_out]
    sky = sample.sky[sample.held_out]
    angular, pixels = residuals(geometry, xy, sky)
    return CatalogCheck(
        geometry,
        _stats(pixels),
        _stats(pixels[outer_stars(xy, size)]),
        float(np.percentile(angular, 95)),
        inverse_error,
    )


def _fit_panel(
    sample: PanelSample, training: Mask, context: JobContext
) -> tuple[dict[str, CatalogCheck], dict[str, str]]:
    original = sample.panel.geometry
    size = sample.panel.size
    if not _supported(sample.xy[sample.held_out], size):
        raise ValueError("The reserved Gaia stars lack detector-wide or outer support.")
    parity = int(np.sign(np.linalg.det(original.wcs.pixel_scale_matrix)))
    saved = _check_catalog(original, sample, parity, context)
    anchor_sky = original.wcs.pixel_to_world(*(original.wcs.wcs.crpix - 1)).icrs
    anchor = float(anchor_sky.ra.deg), float(anchor_sky.dec.deg)
    tangent = tan_output_wcs(anchor, (1, 1), 3600, 0, Region(0, 0, 1, 1))
    sky = sample.sky[training]
    projected = np.column_stack(tangent.wcs_world2pix(sky.ra.deg, sky.dec.deg, 0)) * (-1, 1)
    fitted = {"saved_wcs": saved}
    rejected = {}
    xy = sample.xy[training]
    for model, order in _MODELS.items():
        if len(xy) < _TRAINING_FLOORS[order] or not _supported(xy, size):
            rejected[model] = "Insufficient detector-wide training support."
            continue
        try:
            geometry = _fit(xy, projected, anchor, size, order, context)
            fitted[model] = _check_catalog(geometry, sample, parity, context)
        except (ValueError, OverflowError, np.linalg.LinAlgError) as error:
            rejected[model] = str(error)
    return fitted, rejected


def _overlap_pixels(geometry: PanelGeometry, xy: Pixels, output: PanelGeometry) -> Pixels:
    return output.inverse(geometry.forward(*xy.T))


def _overlap_check(
    matches: MatchedStars,
    held: Mask,
    outer: Mask,
    blocks: Indices,
    left: PanelGeometry,
    right: PanelGeometry,
    output: PanelGeometry,
) -> tuple[dict[str, Stats | None], list[dict[str, object]]]:
    left_xy = _overlap_pixels(left, matches.left_source, output)
    right_xy = _overlap_pixels(right, matches.right_source, output)
    errors = np.linalg.norm(left_xy - right_xy, axis=1)
    if not np.isfinite(errors).all():
        raise QualityRejected("The candidate has nonfinite overlap coordinates.")
    metrics = {
        "all_matches": _stats(errors),
        "outer_matches": _stats(errors[outer]) if outer.any() else None,
        "held_out": _stats(errors[held]) if held.any() else None,
        "held_out_outer": _stats(errors[held & outer]) if (held & outer).any() else None,
    }
    regions: list[dict[str, object]] = []
    for cell in range(9):
        inside = blocks == cell
        independent = inside & held
        regions.append(
            {
                "row": cell // 3,
                "column": cell % 3,
                "matches": int(inside.sum()),
                "held_out_matches": int(independent.sum()),
                "all_matches_p95_px": float(np.percentile(errors[inside], 95))
                if inside.sum() >= 5
                else None,
                "held_out_p95_px": float(np.percentile(errors[independent], 95))
                if independent.sum() >= 5
                else None,
            }
        )
    return metrics, regions


def _catalog_improves(candidate: CatalogCheck, saved: CatalogCheck) -> bool:
    outer_allowance = max(0.05, 0.02 * saved.outer["p95_px"])
    return (
        candidate.overall["p95_px"] <= 0.9 * saved.overall["p95_px"]
        and candidate.outer["p95_px"] <= saved.outer["p95_px"] + outer_allowance
    )


def _candidate_report(
    left: PanelSample,
    right: PanelSample,
    output: PanelGeometry,
    output_size: tuple[int, int],
    context: JobContext,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    samples = (left, right)
    reserved = {
        key
        for sample in samples
        for key, held in zip(sample.keys, sample.held_out, strict=True)
        if held
    }
    training = tuple(
        np.array([key not in reserved for key in sample.keys], dtype=bool) for sample in samples
    )
    (left_fit, left_rejected), (right_fit, right_rejected) = (
        _fit_panel(sample, selected, context)
        for sample, selected in zip(samples, training, strict=True)
    )
    matches = match_stars(left.panel, right.panel, output, output_size)
    _, _, blocks = overlap_blocks(matches.left_output)
    if blocks is None:
        raise ValueError("The overlap has no two-dimensional support.")
    held = np.ones(len(matches.left_source), dtype=bool)
    outer = np.zeros(len(held), dtype=bool)
    for sample, selected, xy in zip(
        samples, training, (matches.left_source, matches.right_source), strict=True
    ):
        excluded = np.vstack((sample.raw_centroids, sample.xy[selected]))
        held &= _outside_centroids(xy, excluded)
        outer |= outer_stars(xy, sample.panel.size)

    overlap: dict[str, object] = {}
    for model in ("saved_wcs", *_MODELS):
        if model not in left_fit or model not in right_fit:
            overlap[model] = {"status": "one or both panels lack a supported fit"}
            continue
        a, b = left_fit[model], right_fit[model]
        try:
            metrics, regions = _overlap_check(
                matches, held, outer, blocks, a.geometry, b.geometry, output
            )
        except QualityRejected as error:
            overlap[model] = {"status": str(error)}
            continue
        all_held, outer_held = metrics["held_out"], metrics["held_out_outer"]
        supported = meets_target = False
        if all_held is not None and outer_held is not None:
            supported = (
                all_held["matches"] >= MIN_MATCHES and outer_held["matches"] >= _MIN_OUTER_MATCHES
            )
            meets_target = (
                supported and max(all_held["p95_px"], outer_held["p95_px"]) < _OVERLAP_TARGET_PX
            )
        overlap[model] = {
            **metrics,
            "regions": regions,
            "independent_overlap_supported": supported,
            "meets_overlap_target": meets_target,
            "eligible": model != "saved_wcs"
            and meets_target
            and _catalog_improves(a, left_fit["saved_wcs"])
            and _catalog_improves(b, right_fit["saved_wcs"]),
        }

    panels = []
    for sample, selected, fitted, rejected in zip(
        samples, training, (left_fit, right_fit), (left_rejected, right_rejected), strict=True
    ):
        panels.append(
            {
                "raw_solver_detections": len(sample.raw_centroids),
                "unclipped_catalog_matches": len(sample.xy),
                "chance_control_matches": sample.chance_matches,
                "training_matches": int(selected.sum()),
                "held_out_matches_by_detector_cell": np.bincount(
                    cells(sample.xy[sample.held_out], sample.panel.size, 3), minlength=9
                ).tolist(),
                "catalog_candidates": {
                    name: {
                        "held_out_source_pixels": fit.overall,
                        "held_out_outer_source_pixels": fit.outer,
                        "held_out_p95_arcsec": fit.p95_arcsec,
                        "maximum_inverse_error_source_px": fit.maximum_inverse_error_px,
                    }
                    for name, fit in fitted.items()
                },
                "rejected_catalog_candidates": rejected,
            }
        )
    return panels, overlap


def measure(project_path: Path, catalog_path: Path) -> dict[str, object]:
    import seiza

    project = load_project(project_path)
    context = JobContext()
    budget = project.render.max_working_bytes
    indices = project.sky_indices()
    if len(indices) != 2 or project.refinement is not None:
        raise ValueError("Use a two-panel photo project with relative refinement off.")
    if len(project_sky_bands(project, context)) != 1:
        raise ValueError("Select two panels in the same sky band.")
    preview = preview_project(project, context, allow_visual=True)
    if preview.output_wcs is None or not preview.visual_only:
        raise ValueError("The original panels must resolve to a visual sky grid.")
    output = PanelGeometry(preview.output_wcs, ICRS())
    output_size = preview.output_size
    scale = (preview.fitted_grid or project.render).scale_arcsec
    del preview
    records = [project.panels[index] for index in indices]
    fingerprints = {
        path: _sha256(path)
        for path in (
            project_path,
            catalog_path,
            *(ref.path for record in records for _, ref in record.references()),
        )
    }
    catalog = seiza.StarCatalog.open(catalog_path)
    catalog_prefix = f"{catalog_path.name} ({catalog_path.stat().st_size} bytes,"

    def query(region: CatalogRegion) -> list[CatalogStar]:
        return [
            CatalogStar(f"{ra:.15g}/{dec:.15g}", ra, dec, mag)
            for ra, dec, mag in catalog.cone_search(
                *region.center, region.radius_deg, limit=max(256, 6 * region.detected_stars)
            )
        ]

    with ExitStack() as opened:
        samples = []
        sources = []
        for record in records:
            if record.wcs_sidecar is None:
                raise ValueError("Use a saved Gaia DR3 WCS sidecar for each panel.")
            sidecar = record.wcs_sidecar.path
            source = opened.enter_context(open_project_sky_panel(record, budget, context))
            geometry, provenance = load_solution(sidecar, source)
            _, attempts = read_solution_diagnostics(sidecar)
            if not provenance.startswith("gaia-dr3 ") or not any(
                attempt.get("stage") == "gaia-dr3"
                and attempt.get("outcome") == "solved"
                and str(attempt.get("catalog")).startswith(catalog_prefix)
                for attempt in attempts
            ):
                raise ValueError(f"{record.source.path.name} requires its saved Gaia catalog.")
            samples.append(_sample_panel(source, geometry, budget, query, context))
            sources.append(
                {
                    "name": record.source.path.name,
                    "sha256": fingerprints[record.source.path],
                    "wcs_sidecar_sha256": fingerprints[sidecar],
                }
            )
        left, right = samples
        panels, overlap = _candidate_report(left, right, output, output_size, context)
    if any(_sha256(path) != digest for path, digest in fingerprints.items()):
        raise ValueError("A project, source, sidecar, mask or catalog changed during validation.")
    return {
        "sources": [{**source, **panel} for source, panel in zip(sources, panels, strict=True)],
        "catalog_sha256": fingerprints[catalog_path],
        "project_sha256": fingerprints[project_path],
        "output_size": output_size,
        "output_scale_arcsec": scale,
        "overlap_target_px": _OVERLAP_TARGET_PX,
        "overlap_candidates": overlap,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Saved two-panel photo project")
    parser.add_argument("--catalog", required=True, type=Path, help="Local Seiza Gaia star catalog")
    arguments = parser.parse_args()
    try:
        report = measure(arguments.project, arguments.catalog)
    except (OSError, ValueError, ImportError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
